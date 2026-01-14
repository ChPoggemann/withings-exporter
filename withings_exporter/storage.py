"""Database storage for Withings health data."""

import json
import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

sqlite3.register_adapter(datetime, lambda value: value.isoformat())
sqlite3.register_adapter(date, lambda value: value.isoformat())


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code.

    Args:
        obj: Object to serialize

    Returns:
        Serializable representation
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # Handle timezone objects
    if hasattr(obj, '__class__') and 'tz' in str(type(obj)):
        return str(obj)
    # Try to convert to string as last resort
    try:
        return str(obj)
    except:
        raise TypeError(f"Type {type(obj)} not serializable")


class HealthDataStorage:
    """SQLite storage for Withings health data."""

    def __init__(self, database_path: Path):
        """Initialize database connection.

        Args:
            database_path: Path to SQLite database file
        """
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(database_path))
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create database schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # Measurements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                measure_type TEXT NOT NULL,
                value REAL,
                unit TEXT,
                device_id TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp, measure_type)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_measurements_type ON measurements(measure_type)")

        # Activity summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                steps INTEGER,
                distance REAL,
                calories REAL,
                elevation REAL,
                soft_activity_duration INTEGER,
                moderate_activity_duration INTEGER,
                intense_activity_duration INTEGER,
                active_calories REAL,
                total_calories REAL,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_summary(date)")

        # Activity intraday table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_intraday (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                steps INTEGER,
                calories REAL,
                elevation REAL,
                distance REAL,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_intraday_timestamp ON activity_intraday(timestamp)")

        # Sleep summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sleep_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                duration INTEGER,
                quality INTEGER,
                deep_duration INTEGER,
                light_duration INTEGER,
                rem_duration INTEGER,
                awake_duration INTEGER,
                heart_rate_avg REAL,
                heart_rate_min REAL,
                heart_rate_max REAL,
                respiration_rate_avg REAL,
                snoring_duration INTEGER,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(start_time)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sleep_start_time ON sleep_summary(start_time)")

        # Heart rate table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS heart_rate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                heart_rate INTEGER,
                device_id TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_heart_rate_timestamp ON heart_rate(timestamp)")

        # Sync state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                data_type TEXT PRIMARY KEY,
                last_sync DATETIME,
                last_data_timestamp DATETIME,
                status TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        logger.info(f"Database schema initialized at {self.database_path}")

    def store_measurements(self, measurements: List[Dict[str, Any]]):
        """Store measurement data.

        Args:
            measurements: List of measurement dictionaries
        """
        cursor = self.conn.cursor()
        stored_count = 0

        for measurement in measurements:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO measurements
                    (timestamp, measure_type, value, unit, device_id, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    measurement.get('timestamp'),
                    measurement.get('measure_type'),
                    measurement.get('value'),
                    measurement.get('unit'),
                    measurement.get('device_id'),
                    json.dumps(measurement.get('raw_data'), default=json_serial)
                ))
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing measurement: {e}")

        self.conn.commit()
        logger.info(f"Stored {stored_count} measurements")

    def store_activity_summary(self, activities: List[Dict[str, Any]]):
        """Store activity summary data.

        Args:
            activities: List of activity summary dictionaries
        """
        cursor = self.conn.cursor()
        stored_count = 0

        for activity in activities:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO activity_summary
                    (date, steps, distance, calories, elevation,
                     soft_activity_duration, moderate_activity_duration,
                     intense_activity_duration, active_calories, total_calories, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    activity.get('date'),
                    activity.get('steps'),
                    activity.get('distance'),
                    activity.get('calories'),
                    activity.get('elevation'),
                    activity.get('soft_activity_duration'),
                    activity.get('moderate_activity_duration'),
                    activity.get('intense_activity_duration'),
                    activity.get('active_calories'),
                    activity.get('total_calories'),
                    json.dumps(activity.get('raw_data'), default=json_serial)
                ))
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing activity: {e}")

        self.conn.commit()
        logger.info(f"Stored {stored_count} activity summaries")

    def store_sleep_summary(self, sleep_sessions: List[Dict[str, Any]]):
        """Store sleep summary data.

        Args:
            sleep_sessions: List of sleep session dictionaries
        """
        cursor = self.conn.cursor()
        stored_count = 0

        for session in sleep_sessions:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO sleep_summary
                    (start_time, end_time, duration, quality, deep_duration,
                     light_duration, rem_duration, awake_duration,
                     heart_rate_avg, heart_rate_min, heart_rate_max,
                     respiration_rate_avg, snoring_duration, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.get('start_time'),
                    session.get('end_time'),
                    session.get('duration'),
                    session.get('quality'),
                    session.get('deep_duration'),
                    session.get('light_duration'),
                    session.get('rem_duration'),
                    session.get('awake_duration'),
                    session.get('heart_rate_avg'),
                    session.get('heart_rate_min'),
                    session.get('heart_rate_max'),
                    session.get('respiration_rate_avg'),
                    session.get('snoring_duration'),
                    json.dumps(session.get('raw_data'), default=json_serial)
                ))
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing sleep session: {e}")

        self.conn.commit()
        logger.info(f"Stored {stored_count} sleep sessions")

    def store_heart_rate(self, heart_rates: List[Dict[str, Any]]):
        """Store heart rate data.

        Args:
            heart_rates: List of heart rate dictionaries
        """
        cursor = self.conn.cursor()
        stored_count = 0

        for hr in heart_rates:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO heart_rate
                    (timestamp, heart_rate, device_id, raw_data)
                    VALUES (?, ?, ?, ?)
                """, (
                    hr.get('timestamp'),
                    hr.get('heart_rate'),
                    hr.get('device_id'),
                    json.dumps(hr.get('raw_data'), default=json_serial)
                ))
                stored_count += 1
            except Exception as e:
                logger.error(f"Error storing heart rate: {e}")

        self.conn.commit()
        logger.info(f"Stored {stored_count} heart rate measurements")

    def update_sync_state(self, data_type: str, last_data_timestamp: Optional[datetime] = None,
                         status: str = "success"):
        """Update sync state for a data type.

        Args:
            data_type: Type of data synced
            last_data_timestamp: Timestamp of the most recent data
            status: Sync status (success, error, etc.)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO sync_state
            (data_type, last_sync, last_data_timestamp, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_type,
            datetime.now(),
            last_data_timestamp,
            status,
            datetime.now()
        ))
        self.conn.commit()

    def get_sync_state(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Get sync state for a data type.

        Args:
            data_type: Type of data

        Returns:
            Sync state dictionary or None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE data_type = ?", (data_type,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_all_measurements(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get all measurements within date range.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of measurement dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM measurements WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"
        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_all_activity(self, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get all activity data within date range.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of activity dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM activity_summary WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date.date() if isinstance(start_date, datetime) else start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date.date() if isinstance(end_date, datetime) else end_date)

        query += " ORDER BY date"
        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_all_sleep(self, start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get all sleep data within date range.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of sleep session dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM sleep_summary WHERE 1=1"
        params = []

        if start_date:
            query += " AND start_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND start_time <= ?"
            params.append(end_date)

        query += " ORDER BY start_time"
        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_all_heart_rate(self, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get all heart rate data within date range.

        Args:
            start_date: Start date filter
            end_date: End date filter

        Returns:
            List of heart rate dictionaries
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM heart_rate WHERE 1=1"
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp"
        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics.

        Returns:
            Dictionary with record counts per table
        """
        cursor = self.conn.cursor()
        stats = {}

        tables = ['measurements', 'activity_summary', 'sleep_summary',
                 'heart_rate']

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]

        return stats

    def close(self):
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
