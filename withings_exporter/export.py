"""Export health data to various formats."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import HealthDataStorage

logger = logging.getLogger(__name__)


class DataExporter:
    """Export health data from database."""

    def __init__(self, storage: HealthDataStorage, export_path: Path):
        """Initialize exporter.

        Args:
            storage: Database storage instance
            export_path: Directory for exports
        """
        self.storage = storage
        self.export_path = export_path
        self.export_path.mkdir(parents=True, exist_ok=True)

    def export_to_json(self, output_file: Optional[str] = None,
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      include_metadata: bool = True,
                      pretty_print: bool = True) -> Path:
        """Export all data to JSON format optimized for LLM consumption.

        Args:
            output_file: Output filename (optional, auto-generated if None)
            start_date: Start date filter
            end_date: End date filter
            include_metadata: Include export metadata
            pretty_print: Pretty print JSON

        Returns:
            Path to exported file
        """
        logger.info("Exporting data to JSON...")

        # Generate filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"withings_export_{timestamp}.json"

        output_path = self.export_path / output_file

        # Collect all data
        export_data = {}

        # Add metadata
        if include_metadata:
            export_data['export_metadata'] = {
                'export_time': datetime.now().isoformat(),
                'date_range': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                },
                'data_types': ['measurements', 'activity', 'sleep', 'heart_rate'],
                'database_stats': self.storage.get_statistics()
            }

        # Export measurements
        measurements_data = self._export_measurements(start_date, end_date)
        if measurements_data:
            export_data['measurements'] = measurements_data

        # Export activity
        activity_data = self._export_activity(start_date, end_date)
        if activity_data:
            export_data['activity'] = activity_data

        # Export sleep
        sleep_data = self._export_sleep(start_date, end_date)
        if sleep_data:
            export_data['sleep'] = sleep_data

        # Export heart rate
        heart_rate_data = self._export_heart_rate(start_date, end_date)
        if heart_rate_data:
            export_data['heart_rate'] = heart_rate_data

        # Write to file
        with open(output_path, 'w') as f:
            if pretty_print:
                json.dump(export_data, f, indent=2, default=str)
            else:
                json.dump(export_data, f, default=str)

        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"Exported data to {output_path} ({file_size:.2f} MB)")

        return output_path

    def _export_measurements(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """Export measurements grouped by type.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Dictionary of measurements by type
        """
        measurements = self.storage.get_all_measurements(start_date, end_date)

        # Group by measure type
        grouped = {}
        for measurement in measurements:
            measure_type = measurement['measure_type']

            if measure_type not in grouped:
                grouped[measure_type] = []

            grouped[measure_type].append({
                'timestamp': measurement['timestamp'],
                'value': measurement['value'],
                'unit': measurement['unit'],
                'device_id': measurement['device_id']
            })

        # Sort each type by timestamp
        for measure_type in grouped:
            grouped[measure_type].sort(key=lambda x: x['timestamp'])

        return grouped

    def _export_activity(self, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Export activity data.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Dictionary of activity data
        """
        activities = self.storage.get_all_activity(start_date, end_date)

        # Create daily summary
        daily_summary = []
        for activity in activities:
            daily_summary.append({
                'date': str(activity['date']),
                'steps': activity['steps'],
                'distance': activity['distance'],
                'calories': activity['calories'],
                'elevation': activity['elevation'],
                'activity_duration': {
                    'soft': activity['soft_activity_duration'],
                    'moderate': activity['moderate_activity_duration'],
                    'intense': activity['intense_activity_duration']
                }
            })

        # Calculate statistics
        if daily_summary:
            stats = {
                'total_days': len(daily_summary),
                'avg_steps': sum(d['steps'] or 0 for d in daily_summary) / len(daily_summary),
                'total_distance': sum(d['distance'] or 0 for d in daily_summary),
                'total_calories': sum(d['calories'] or 0 for d in daily_summary)
            }
        else:
            stats = {}

        return {
            'daily_summary': daily_summary,
            'statistics': stats
        }

    def _export_sleep(self, start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Export sleep data.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Dictionary of sleep data
        """
        sleep_sessions = self.storage.get_all_sleep(start_date, end_date)

        # Create sessions list
        sessions = []
        for session in sleep_sessions:
            sessions.append({
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'duration': session['duration'],
                'quality': session['quality'],
                'sleep_stages': {
                    'deep': session['deep_duration'],
                    'light': session['light_duration'],
                    'rem': session['rem_duration'],
                    'awake': session['awake_duration']
                },
                'vitals': {
                    'heart_rate_avg': session['heart_rate_avg'],
                    'heart_rate_min': session['heart_rate_min'],
                    'heart_rate_max': session['heart_rate_max'],
                    'respiration_rate_avg': session['respiration_rate_avg']
                },
                'snoring_duration': session['snoring_duration']
            })

        # Calculate statistics
        if sessions:
            total_sleep_time = sum(s['duration'] or 0 for s in sessions)
            stats = {
                'total_sessions': len(sessions),
                'avg_duration': total_sleep_time / len(sessions),
                'total_sleep_time': total_sleep_time,
                'avg_quality': sum(s['quality'] or 0 for s in sessions if s['quality']) / len([s for s in sessions if s['quality']]) if any(s['quality'] for s in sessions) else None
            }
        else:
            stats = {}

        return {
            'sessions': sessions,
            'statistics': stats
        }

    def _export_heart_rate(self, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Export heart rate data.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Dictionary of heart rate data
        """
        heart_rates = self.storage.get_all_heart_rate(start_date, end_date)

        records = []
        for hr in heart_rates:
            records.append({
                'timestamp': hr['timestamp'],
                'heart_rate': hr['heart_rate'],
                'device_id': hr['device_id']
            })

        if records:
            avg_hr = sum(r['heart_rate'] or 0 for r in records) / len(records)
            stats = {
                'total_records': len(records),
                'avg_heart_rate': avg_hr
            }
        else:
            stats = {}

        return {
            'records': records,
            'statistics': stats
        }

    def export_measurements_csv(self, output_file: Optional[str] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Path:
        """Export measurements to CSV format.

        Args:
            output_file: Output filename
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Path to exported file
        """
        import csv

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"measurements_{timestamp}.csv"

        output_path = self.export_path / output_file

        measurements = self.storage.get_all_measurements(start_date, end_date)

        with open(output_path, 'w', newline='') as f:
            if measurements:
                fieldnames = ['timestamp', 'measure_type', 'value', 'unit', 'device_id']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for measurement in measurements:
                    writer.writerow({
                        'timestamp': measurement['timestamp'],
                        'measure_type': measurement['measure_type'],
                        'value': measurement['value'],
                        'unit': measurement['unit'],
                        'device_id': measurement['device_id']
                    })

        logger.info(f"Exported measurements to {output_path}")
        return output_path

    def export_activity_csv(self, output_file: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> Path:
        """Export activity data to CSV format.

        Args:
            output_file: Output filename
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Path to exported file
        """
        import csv

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"activity_{timestamp}.csv"

        output_path = self.export_path / output_file

        activities = self.storage.get_all_activity(start_date, end_date)

        with open(output_path, 'w', newline='') as f:
            if activities:
                fieldnames = ['date', 'steps', 'distance', 'calories', 'elevation',
                            'soft_activity_duration', 'moderate_activity_duration',
                            'intense_activity_duration']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for activity in activities:
                    writer.writerow({k: activity.get(k) for k in fieldnames})

        logger.info(f"Exported activity to {output_path}")
        return output_path

    def export_sleep_csv(self, output_file: Optional[str] = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Path:
        """Export sleep data to CSV format.

        Args:
            output_file: Output filename
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Path to exported file
        """
        import csv

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"sleep_{timestamp}.csv"

        output_path = self.export_path / output_file

        sleep_sessions = self.storage.get_all_sleep(start_date, end_date)

        with open(output_path, 'w', newline='') as f:
            if sleep_sessions:
                fieldnames = ['start_time', 'end_time', 'duration', 'quality',
                            'deep_duration', 'light_duration', 'rem_duration',
                            'awake_duration', 'heart_rate_avg', 'respiration_rate_avg']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for session in sleep_sessions:
                    writer.writerow({k: session.get(k) for k in fieldnames})

        logger.info(f"Exported sleep to {output_path}")
        return output_path

    def export_heart_rate_csv(self, output_file: Optional[str] = None,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Path:
        """Export heart rate data to CSV format.

        Args:
            output_file: Output filename
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Path to exported file
        """
        import csv

        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"heart_rate_{timestamp}.csv"

        output_path = self.export_path / output_file

        heart_rates = self.storage.get_all_heart_rate(start_date, end_date)

        with open(output_path, 'w', newline='') as f:
            if heart_rates:
                fieldnames = ['timestamp', 'heart_rate', 'device_id']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for hr in heart_rates:
                    writer.writerow({k: hr.get(k) for k in fieldnames})

        logger.info(f"Exported heart rate to {output_path}")
        return output_path
