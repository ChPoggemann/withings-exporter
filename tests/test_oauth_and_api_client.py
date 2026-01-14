import requests

from withings_exporter.api_client import (
    WithingsAPIClient,
    WithingsAuthError,
    WithingsRateLimitError,
)
from withings_exporter.oauth_client import WithingsOAuthClient, OAuthToken, WithingsOAuthError


class DummyResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text
        self.headers = {"Content-Type": "application/json"}

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self._json_body, Exception):
            raise self._json_body
        return self._json_body


def test_oauth_refresh_non_json_raises(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    client = WithingsOAuthClient(
        client_id="client",
        client_secret="secret",
        callback_uri="http://localhost:8080",
        token_storage_path=token_path,
        auto_refresh=True,
    )
    client.token = OAuthToken(
        access_token="access",
        refresh_token="refresh",
        token_type="Bearer",
        expires_in=3600,
        token_expiry=0,
    )

    def fake_post(*_args, **_kwargs):
        return DummyResponse(
            status_code=200,
            json_body=requests.exceptions.JSONDecodeError("bad", "doc", 0),
            text="<html>login</html>",
        )

    monkeypatch.setattr("withings_exporter.oauth_client.requests.post", fake_post)

    try:
        client.refresh_access_token()
        assert False, "Expected WithingsOAuthError"
    except WithingsOAuthError as exc:
        assert "Non-JSON" in str(exc)


def test_api_client_rate_limit_retries(monkeypatch):
    client = WithingsAPIClient(access_token="access")
    calls = {"count": 0}

    def fake_get(*_args, **_kwargs):
        calls["count"] += 1
        body = {"status": 601, "body": {}}
        return DummyResponse(json_body=body)

    monkeypatch.setattr("withings_exporter.api_client.requests.get", fake_get)
    monkeypatch.setattr("withings_exporter.api_client.time.sleep", lambda *_: None)

    try:
        client.get_measurements()
        assert False, "Expected WithingsRateLimitError"
    except WithingsRateLimitError:
        pass

    assert calls["count"] == 4


def test_api_client_auth_error(monkeypatch):
    client = WithingsAPIClient(access_token="access")

    def fake_get(*_args, **_kwargs):
        body = {"status": 401, "body": {}}
        return DummyResponse(json_body=body)

    monkeypatch.setattr("withings_exporter.api_client.requests.get", fake_get)

    try:
        client.get_measurements()
        assert False, "Expected WithingsAuthError"
    except WithingsAuthError:
        pass
