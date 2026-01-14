"""Data fetcher for Withings API."""

import logging
from datetime import datetime, timedelta, date
from typing import Any, Callable, Dict, List, Optional

from .api_client import WithingsAPIClient, WithingsAPIError
from .oauth_client import OAuthToken
from .storage import HealthDataStorage

logger = logging.getLogger(__name__)


class WithingsDataFetcher:
    """Fetches health data from Withings API."""

    # Maximum days per request for historical data
    MAX_DAYS_PER_REQUEST = 200

    def __init__(self, token: OAuthToken, storage: HealthDataStorage,
                 token_refresh_callback: Optional[Callable] = None):
        """Initialize data fetcher.

        Args:
            token: OAuth token
            storage: Database storage instance
            token_refresh_callback: Optional callback for token refresh
        """
        self.token = token
        self.storage = storage
        self.token_refresh_callback = token_refresh_callback

        # Create API client
        self.api = WithingsAPIClient(
            access_token=token.access_token,
            token_refresh_callback=self._handle_token_refresh
        )

    def _handle_token_refresh(self, new_token: OAuthToken):
        """Handle token refresh from API client.

        Args:
            new_token: Refreshed OAuth token
        """
        self.token = new_token
        self.api.access_token = new_token.access_token

        if self.token_refresh_callback:
            self.token_refresh_callback(new_token)

        logger.info("API credentials refreshed")

    def fetch_all_data(self, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      data_types: Optional[Dict[str, bool]] = None):
        """Fetch all enabled data types.

        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch
            data_types: Dictionary of data types to fetch
        """
        if not end_date:
            end_date = datetime.now()

        # Default to fetching all data types
        if not data_types:
            data_types = {
                'measurements': True,
                'activity': True,
                'sleep': True,
                'heart_rate': True
            }

        logger.info(f"Starting data fetch from {start_date} to {end_date}")

        if data_types.get('measurements', False):
            self.fetch_measurements(
                start_date,
                end_date,
                store_heart_rate=data_types.get('heart_rate', True)
            )

        if data_types.get('activity', False):
            self.fetch_activity(start_date, end_date)

        if data_types.get('sleep', False):
            self.fetch_sleep(start_date, end_date)

        logger.info("Data fetch completed")

    def fetch_measurements(self, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          store_heart_rate: bool = True):
        """Fetch measurement data (weight, body composition, etc.).

        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch
            store_heart_rate: Store heart rate readings from measurements
        """
        logger.info("Fetching measurements...")

        try:
            # Check last sync
            sync_state = self.storage.get_sync_state('measurements')
            if not start_date and sync_state:
                start_date = sync_state.get('last_data_timestamp')
                if start_date:
                    start_date = datetime.fromisoformat(start_date)
                    logger.info(f"Resuming from last sync: {start_date}")

            # Convert datetime to Unix timestamp if provided
            startdate_ts = int(start_date.timestamp()) if start_date else None
            enddate_ts = int(end_date.timestamp()) if end_date else None

            measurements = []
            heart_rates = []
            last_timestamp = None
            offset = None
            seen_offsets = set()

            while True:
                result = self.api.get_measurements(
                    startdate=startdate_ts,
                    enddate=enddate_ts,
                    category=1,
                    offset=offset
                )

                measuregrps = result.get('measuregrps', [])
                logger.info(f"API returned {len(measuregrps)} measurement groups")

                for measure_group in measuregrps:
                    # Parse Unix timestamp to datetime
                    timestamp = datetime.fromtimestamp(measure_group['date'])
                    device_id = measure_group.get('deviceid')

                    for measure in measure_group.get('measures', []):
                        measure_type = measure['type']
                        measure_type_name = self._get_measure_type_name(measure_type)

                        # Calculate real value: value * 10^unit
                        real_value = measure['value'] * (10 ** measure['unit'])

                        measurement = {
                            'timestamp': timestamp,
                            'measure_type': measure_type_name,
                            'value': real_value,
                            'unit': self._get_measure_unit(measure_type),
                            'device_id': device_id,
                            'raw_data': {
                                'type': measure_type,
                                'value': measure['value'],
                                'unit': measure['unit'],
                                'grpid': measure_group.get('grpid')
                            }
                        }
                        measurements.append(measurement)

                        if store_heart_rate and measure_type == 11:
                            heart_rates.append({
                                'timestamp': timestamp,
                                'heart_rate': real_value,
                                'device_id': device_id,
                                'raw_data': measurement['raw_data']
                            })

                        if not last_timestamp or timestamp > last_timestamp:
                            last_timestamp = timestamp

                if not result.get('more'):
                    break

                offset = result.get('offset')
                if offset is None or offset in seen_offsets:
                    logger.warning("Measurement pagination ended unexpectedly; stopping early.")
                    break
                seen_offsets.add(offset)

            # Store measurements
            if measurements:
                self.storage.store_measurements(measurements)
                if heart_rates:
                    self.storage.store_heart_rate(heart_rates)
                self.storage.update_sync_state('measurements', last_timestamp, 'success')
                logger.info(f"Fetched {len(measurements)} measurements")
            else:
                logger.info("No new measurements found")
                self.storage.update_sync_state('measurements', status='success')

        except WithingsAPIError as e:
            logger.error(f"API error fetching measurements: {e}", exc_info=True)
            self.storage.update_sync_state('measurements', status='error')
        except Exception as e:
            logger.error(f"Error fetching measurements: {e}", exc_info=True)
            self.storage.update_sync_state('measurements', status='error')

    def fetch_activity(self, start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None):
        """Fetch activity data.

        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch
        """
        logger.info("Fetching activity data...")

        try:
            # Check last sync
            sync_state = self.storage.get_sync_state('activity')
            if not start_date and sync_state:
                last_sync = sync_state.get('last_data_timestamp')
                if last_sync:
                    start_date = datetime.fromisoformat(last_sync)
                    logger.info(f"Resuming from last sync: {start_date}")

            if not start_date:
                start_date = datetime.now() - timedelta(days=3650)

            if not end_date:
                end_date = datetime.now()

            # Fetch activity in chunks
            current_date = start_date
            all_activities = []

            while current_date < end_date:
                chunk_end = min(current_date + timedelta(days=self.MAX_DAYS_PER_REQUEST), end_date)

                try:
                    # Format dates as YYYY-MM-DD strings
                    startdateymd = current_date.strftime('%Y-%m-%d')
                    enddateymd = chunk_end.strftime('%Y-%m-%d')

                    result = self.api.get_activity(
                        startdateymd=startdateymd,
                        enddateymd=enddateymd
                    )

                    activities_list = result.get('activities', [])

                    for activity in activities_list:
                        # Parse date string to date object
                        activity_date = datetime.strptime(activity['date'], '%Y-%m-%d').date()

                        activity_data = {
                            'date': activity_date,
                            'steps': activity.get('steps'),
                            'distance': activity.get('distance'),
                            'calories': activity.get('calories'),
                            'elevation': activity.get('elevation'),
                            'soft_activity_duration': activity.get('soft'),
                            'moderate_activity_duration': activity.get('moderate'),
                            'intense_activity_duration': activity.get('intense'),
                            'active_calories': activity.get('active'),
                            'total_calories': activity.get('totalcalories'),
                            'raw_data': activity
                        }
                        all_activities.append(activity_data)

                except WithingsAPIError as e:
                    logger.error(f"Error fetching activity chunk {current_date} to {chunk_end}: {e}")

                current_date = chunk_end

            # Store activity data
            if all_activities:
                self.storage.store_activity_summary(all_activities)
                last_date = max(a['date'] for a in all_activities)
                self.storage.update_sync_state('activity', datetime.combine(last_date, datetime.min.time()), 'success')
                logger.info(f"Fetched {len(all_activities)} activity records")
            else:
                logger.info("No new activity data found")
                self.storage.update_sync_state('activity', status='success')

        except Exception as e:
            logger.error(f"Error fetching activity: {e}")
            self.storage.update_sync_state('activity', status='error')

    def fetch_sleep(self, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None):
        """Fetch sleep data.

        Args:
            start_date: Start date for data fetch
            end_date: End date for data fetch
        """
        logger.info("Fetching sleep data...")

        try:
            # Check last sync
            sync_state = self.storage.get_sync_state('sleep')
            if not start_date and sync_state:
                last_sync = sync_state.get('last_data_timestamp')
                if last_sync:
                    start_date = datetime.fromisoformat(last_sync)
                    logger.info(f"Resuming from last sync: {start_date}")

            if not start_date:
                start_date = datetime.now() - timedelta(days=3650)

            if not end_date:
                end_date = datetime.now()

            # Fetch sleep data in chunks
            current_date = start_date
            all_sleep_sessions = []

            # Define all sleep data fields to request
            sleep_fields = [
                'breathing_disturbances_intensity',
                'deepsleepduration',
                'durationtosleep',
                'durationtowakeup',
                'hr_average',
                'hr_max',
                'hr_min',
                'lightsleepduration',
                'remsleepduration',
                'rr_average',
                'rr_max',
                'rr_min',
                'sleep_score',
                'snoring',
                'snoringepisodecount',
                'wakeupcount',
                'wakeupduration'
            ]

            while current_date < end_date:
                chunk_end = min(current_date + timedelta(days=self.MAX_DAYS_PER_REQUEST), end_date)

                try:
                    startdateymd = current_date.strftime('%Y-%m-%d')
                    enddateymd = chunk_end.strftime('%Y-%m-%d')

                    result = self.api.get_sleep_summary(
                        startdateymd=startdateymd,
                        enddateymd=enddateymd,
                        data_fields=sleep_fields
                    )

                    series_list = result.get('series', [])
                    logger.info(f"Sleep API returned {len(series_list)} sleep sessions for chunk {current_date} to {chunk_end}")

                    for sleep_session in series_list:
                        # Parse Unix timestamps to datetime
                        start_time = datetime.fromtimestamp(sleep_session['startdate'])
                        end_time = datetime.fromtimestamp(sleep_session['enddate'])

                        data = sleep_session.get('data', {})

                        sleep_data = {
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': data.get('total_sleep_time') or (end_time - start_time).seconds,
                            'quality': data.get('sleep_score'),
                            'deep_duration': data.get('deepsleepduration'),
                            'light_duration': data.get('lightsleepduration'),
                            'rem_duration': data.get('remsleepduration'),
                            'awake_duration': data.get('wakeupduration'),
                            'heart_rate_avg': data.get('hr_average'),
                            'heart_rate_min': data.get('hr_min'),
                            'heart_rate_max': data.get('hr_max'),
                            'respiration_rate_avg': data.get('rr_average'),
                            'snoring_duration': data.get('snoring'),
                            'raw_data': sleep_session
                        }
                        all_sleep_sessions.append(sleep_data)

                except WithingsAPIError as e:
                    logger.error(f"Error fetching sleep chunk {current_date} to {chunk_end}: {e}")

                current_date = chunk_end

            # Store sleep data
            if all_sleep_sessions:
                self.storage.store_sleep_summary(all_sleep_sessions)
                last_timestamp = max(s['start_time'] for s in all_sleep_sessions)
                self.storage.update_sync_state('sleep', last_timestamp, 'success')
                logger.info(f"Fetched {len(all_sleep_sessions)} sleep sessions")
            else:
                logger.info("No new sleep data found")
                self.storage.update_sync_state('sleep', status='success')

        except Exception as e:
            logger.error(f"Error fetching sleep: {e}", exc_info=True)
            self.storage.update_sync_state('sleep', status='error')

    def _get_measure_type_name(self, measure_type: int) -> str:
        """Get human-readable measure type name.

        Args:
            measure_type: Numeric measure type

        Returns:
            Measure type name
        """
        measure_map = {
            1: 'weight',
            4: 'height',
            5: 'fat_free_mass',
            6: 'fat_ratio',
            8: 'fat_mass',
            9: 'diastolic_blood_pressure',
            10: 'systolic_blood_pressure',
            11: 'heart_rate',
            12: 'temperature',
            54: 'spo2',
            71: 'body_temperature',
            73: 'skin_temperature',
            76: 'muscle_mass',
            77: 'hydration',
            88: 'bone_mass',
            91: 'pulse_wave_velocity',
            123: 'vo2_max',
            155: 'vascular_age',
        }
        return measure_map.get(measure_type, f'unknown_{measure_type}')

    def _get_measure_unit(self, measure_type: int) -> str:
        """Get unit for measure type.

        Args:
            measure_type: Numeric measure type

        Returns:
            Unit string
        """
        unit_map = {
            1: 'kg',
            4: 'm',
            5: 'kg',
            6: '%',
            8: 'kg',
            9: 'mmHg',
            10: 'mmHg',
            11: 'bpm',
            12: '°C',
            54: '%',
            71: '°C',
            73: '°C',
            76: 'kg',
            77: 'kg',
            88: 'kg',
            91: 'm/s',
            123: 'ml/min/kg',
            155: 'years',
        }
        return unit_map.get(measure_type, 'unknown')
