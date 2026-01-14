from datetime import datetime

from withings_exporter.fetcher import WithingsDataFetcher
from withings_exporter.oauth_client import OAuthToken
from withings_exporter.storage import HealthDataStorage


def _make_token():
    return OAuthToken(
        access_token="access",
        refresh_token="refresh",
        token_type="Bearer",
        expires_in=3600,
        token_expiry=9999999999,
    )


def test_fetch_measurements_paginates_and_stores_heart_rate(tmp_path):
    db_path = tmp_path / "health_data.db"
    storage = HealthDataStorage(db_path)
    fetcher = WithingsDataFetcher(_make_token(), storage)

    responses = [
        {
            "measuregrps": [
                {
                    "date": 1767225600,
                    "deviceid": "device-1",
                    "measures": [
                        {"type": 1, "value": 70000, "unit": -3},
                        {"type": 11, "value": 60000, "unit": -3},
                    ],
                }
            ],
            "more": True,
            "offset": 123,
        },
        {
            "measuregrps": [
                {
                    "date": 1767312000,
                    "deviceid": "device-1",
                    "measures": [{"type": 1, "value": 71000, "unit": -3}],
                }
            ],
            "more": False,
            "offset": None,
        },
    ]

    def fake_get_measurements(**_):
        return responses.pop(0)

    fetcher.api.get_measurements = fake_get_measurements

    fetcher.fetch_measurements(
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 2),
        store_heart_rate=True,
    )

    measurements = storage.get_all_measurements()
    heart_rates = storage.get_all_heart_rate()
    sync_state = storage.get_sync_state("measurements")

    assert len(measurements) == 3
    assert len(heart_rates) == 1
    assert sync_state["status"] == "success"


def test_fetch_measurements_can_skip_heart_rate(tmp_path):
    db_path = tmp_path / "health_data.db"
    storage = HealthDataStorage(db_path)
    fetcher = WithingsDataFetcher(_make_token(), storage)

    def fake_get_measurements(**_):
        return {
            "measuregrps": [
                {
                    "date": 1767225600,
                    "deviceid": "device-1",
                    "measures": [{"type": 11, "value": 60000, "unit": -3}],
                }
            ],
            "more": False,
            "offset": None,
        }

    fetcher.api.get_measurements = fake_get_measurements

    fetcher.fetch_measurements(store_heart_rate=False)

    heart_rates = storage.get_all_heart_rate()
    assert len(heart_rates) == 0
