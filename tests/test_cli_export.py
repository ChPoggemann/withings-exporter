import os
from pathlib import Path

from click.testing import CliRunner

from withings_exporter.cli import main
from withings_exporter.storage import HealthDataStorage


def test_csv_output_respects_output_dir(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr("withings_exporter.config.Config.setup_logging", lambda *_: None)

    db_path = home_dir / ".withings" / "health_data.db"
    storage = HealthDataStorage(db_path)
    storage.store_measurements([
        {
            "timestamp": "2026-01-01T08:00:00",
            "measure_type": "weight",
            "value": 70.0,
            "unit": "kg",
            "device_id": "device-1",
            "raw_data": {"type": 1},
        }
    ])
    storage.store_activity_summary([
        {
            "date": "2026-01-01",
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
            "start_time": "2026-01-01T22:00:00",
            "end_time": "2026-01-02T06:00:00",
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
            "timestamp": "2026-01-01T08:00:00",
            "heart_rate": 60,
            "device_id": "device-1",
            "raw_data": {"type": 11},
        }
    ])
    storage.close()

    output_dir = tmp_path / "out"
    output_path = output_dir / "custom.csv"

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["export", "--format", "csv", "--output", str(output_path)],
    )
    assert result.exit_code == 0, result.output

    expected = [
        output_dir / "custom_measurements.csv",
        output_dir / "custom_activity.csv",
        output_dir / "custom_sleep.csv",
        output_dir / "custom_heart_rate.csv",
    ]

    for path in expected:
        assert path.exists()
