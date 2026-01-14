"""Native OAuth 2.0 client for Withings API."""

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# OAuth endpoints
OAUTH_AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"
OAUTH_TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"


class OAuthScope:
    """Withings OAuth 2.0 scopes."""

    USER_INFO = "user.info"
    USER_METRICS = "user.metrics"
    USER_ACTIVITY = "user.activity"
    USER_SLEEP_EVENTS = "user.sleepevents"

    @classmethod
    def all_scopes(cls) -> List[str]:
        """Get all available scopes."""
        return [cls.USER_INFO, cls.USER_METRICS, cls.USER_ACTIVITY, cls.USER_SLEEP_EVENTS]


@dataclass
class OAuthToken:
    """OAuth token storage model."""

    access_token: str
    refresh_token: str
    token_type: str  # "Bearer"
    expires_in: int  # seconds (typically 10800 = 3 hours)
    token_expiry: int  # Unix timestamp when token expires
    userid: Optional[int] = None
    scope: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'OAuthToken':
        """Create from API response or stored JSON.

        Args:
            data: Dictionary with token data

        Returns:
            OAuthToken instance
        """
        return cls(
            access_token=data['access_token'],
            refresh_token=data['refresh_token'],
            token_type=data.get('token_type', 'Bearer'),
            expires_in=data.get('expires_in', 10800),
            token_expiry=data.get('token_expiry', int(time.time() + data.get('expires_in', 10800))),
            userid=data.get('userid'),
            scope=data.get('scope')
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage.

        Returns:
            Dictionary representation
        """
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_in': self.expires_in,
            'token_expiry': self.token_expiry,
            'userid': self.userid,
            'scope': self.scope
        }

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or will expire soon.

        Args:
            buffer_seconds: Expire buffer time in seconds (default 5 minutes)

        Returns:
            True if expired or expiring soon
        """
        return int(time.time()) >= (self.token_expiry - buffer_seconds)


class WithingsOAuthError(Exception):
    """OAuth-related errors."""

    def __init__(self, status_code: int, message: str, response: dict = None):
        """Initialize OAuth error.

        Args:
            status_code: Withings API status code
            message: Error message
            response: Full response dict if available
        """
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"OAuth Error {status_code}: {message}")


class WithingsOAuthClient:
    """Handles OAuth 2.0 authentication flow with Withings."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        callback_uri: str,
        token_storage_path: Path,
        auto_refresh: bool = True
    ):
        """Initialize OAuth client.

        Args:
            client_id: Withings API client ID
            client_secret: Withings API client secret
            callback_uri: OAuth callback URI (e.g., http://localhost:8080)
            token_storage_path: Path to store token JSON file
            auto_refresh: Automatically refresh expired tokens
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_uri = callback_uri
        self.token_storage_path = token_storage_path
        self.auto_refresh = auto_refresh
        self.token: Optional[OAuthToken] = None

        self._load_token()

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        if not state:
            state = secrets.token_urlsafe(32)

        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.callback_uri,
            'scope': ','.join(OAuthScope.all_scopes()),
            'state': state
        }

        return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, authorization_code: str) -> OAuthToken:
        """Exchange authorization code for access token.

        Args:
            authorization_code: Authorization code from OAuth callback

        Returns:
            OAuthToken with access and refresh tokens

        Raises:
            WithingsOAuthError: If token exchange fails
        """
        data = {
            'action': 'requesttoken',
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': authorization_code,
            'redirect_uri': self.callback_uri
        }

        headers = {"Accept": "application/json"}
        logger.debug(
            "Requesting OAuth token exchange (client_id=%s, redirect_uri=%s)",
            f"...{self.client_id[-6:]}" if self.client_id else "<missing>",
            self.callback_uri
        )
        response = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()

        try:
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            snippet = response.text[:500] if response.text else "<empty>"
            logger.error(
                "OAuth token exchange returned non-JSON response (status %s, content-type %s): %s",
                response.status_code,
                response.headers.get("Content-Type"),
                snippet
            )
            raise WithingsOAuthError(
                response.status_code,
                "Non-JSON response from token endpoint"
            )
        if result.get('status') != 0:
            raise WithingsOAuthError(
                result.get('status', -1),
                result.get('error', 'Unknown error'),
                result
            )

        body = result['body']
        # Calculate token expiry
        body['token_expiry'] = int(time.time()) + body.get('expires_in', 10800)

        self.token = OAuthToken.from_dict(body)
        self._save_token()

        logger.info("Successfully exchanged authorization code for token")
        return self.token

    def refresh_access_token(self) -> OAuthToken:
        """Refresh access token using refresh token.

        Returns:
            New OAuthToken with refreshed access token

        Raises:
            WithingsOAuthError: If token refresh fails
        """
        if not self.token or not self.token.refresh_token:
            raise WithingsOAuthError(0, "No refresh token available")

        data = {
            'action': 'requesttoken',
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.token.refresh_token
        }

        headers = {"Accept": "application/json"}
        logger.debug(
            "Refreshing OAuth token (client_id=%s)",
            f"...{self.client_id[-6:]}" if self.client_id else "<missing>"
        )
        response = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()

        try:
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            snippet = response.text[:500] if response.text else "<empty>"
            logger.error(
                "OAuth token refresh returned non-JSON response (status %s, content-type %s): %s",
                response.status_code,
                response.headers.get("Content-Type"),
                snippet
            )
            raise WithingsOAuthError(
                response.status_code,
                "Non-JSON response from token endpoint"
            )
        if result.get('status') != 0:
            raise WithingsOAuthError(
                result.get('status', -1),
                result.get('error', 'Token refresh failed'),
                result
            )

        body = result['body']
        body['token_expiry'] = int(time.time()) + body.get('expires_in', 10800)

        # Preserve userid if not in refresh response
        old_userid = self.token.userid
        self.token = OAuthToken.from_dict(body)
        if not self.token.userid:
            self.token.userid = old_userid

        self._save_token()
        logger.info("Access token refreshed successfully")

        return self.token

    def get_valid_token(self) -> OAuthToken:
        """Get valid access token, refreshing if necessary.

        Returns:
            Valid OAuthToken

        Raises:
            WithingsOAuthError: If not authenticated or refresh fails
        """
        if not self.token:
            raise WithingsOAuthError(0, "Not authenticated. Run setup first.")

        if self.token.is_expired() and self.auto_refresh:
            logger.info("Token expired, refreshing...")
            self.refresh_access_token()

        return self.token

    def _load_token(self):
        """Load token from storage file."""
        if self.token_storage_path.exists():
            try:
                with open(self.token_storage_path, 'r') as f:
                    data = json.load(f)
                self.token = OAuthToken.from_dict(data)
                logger.info("Loaded OAuth token from storage")
            except Exception as e:
                logger.error(f"Error loading token: {e}")

    def _save_token(self):
        """Save token to storage file."""
        if not self.token:
            return

        self.token_storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.token_storage_path, 'w') as f:
            json.dump(self.token.to_dict(), f, indent=2)

        # Set secure file permissions (read/write for owner only)
        self.token_storage_path.chmod(0o600)
        logger.info(f"Saved OAuth token to {self.token_storage_path}")
