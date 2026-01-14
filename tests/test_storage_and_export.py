import json
from datetime import datetime, date

from withings_exporter.export import DataExporter
from withings_exporter.storage import HealthDataStorage


def test_storage_and_export_json_includes_heart_rate(tmp_path):
    db_path = tmp_path / "health_data.db"
    export_path = tmp_path / "exports"
    storage = HealthDataStorage(db_path)

    storage.store_measurements([
        {
            "timestamp": datetime(2026, 1, 1, 8, 0, 0),
            "measure_type": "weight",
            "value": 70.0,
            "unit": "kg",
            "device_id": "device-1",
            "raw_data": {"type": 1},
        }
    ])
    storage.store_activity_summary([
        {
            "date": date(2026, 1, 1),
            "steps": 1000,
            "distance": 0.8,
            "calories": 50,
            "elevation": 5,
            "soft_activity_duration": 10,
            "moderate_activity_duration": 5,
            "intense_activity_duration": 0,
            "active_calories": 20,
            "total_calories": 200,
            "raw_data": {"date": "2026-01-01"},
        }
    ])
    storage.store_sleep_summary([
        {
            "start_time": datetime(2026, 1, 1, 22, 0, 0),
            "end_time": datetime(2026, 1, 2, 6, 0, 0),
            "duration": 8 * 60 * 60,
            "quality": 75,
            "deep_duration": 90,
            "light_duration": 200,
            "rem_duration": 80,
            "awake_duration": 20,
            "heart_rate_avg": 55,
            "heart_rate_min": 48,
            "heart_rate_max": 70,
            "respiration_rate_avg": 12,
            "snoring_duration": 0,
            "raw_data": {"startdate": 1700000000},
        }
    ])
    storage.store_heart_rate([
        {
            "timestamp": datetime(2026, 1, 1, 8, 0, 0),
            "heart_rate": 60,
            "device_id": "device-1",
            "raw_data": {"type": 11},
        }
    ])

    exporter = DataExporter(storage, export_path)
    output_path = exporter.export_to_json(pretty_print=False)

    with open(output_path, "r") as f:
        payload = json.load(f)

    assert "heart_rate" in payload
    assert payload["heart_rate"]["records"]
    assert payload["measurements"]["weight"]
