"""OAuth authentication for Withings API."""

import json
import logging
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .oauth_client import WithingsOAuthClient, OAuthToken, OAuthScope

logger = logging.getLogger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    auth_code: Optional[str] = None

    def do_GET(self):
        """Handle GET request from OAuth callback."""
        query_components = parse_qs(urlparse(self.path).query)

        if 'code' in query_components:
            OAuthCallbackHandler.auth_code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Withings Authorization</title></head>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Withings Authorization</title></head>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>No authorization code received.</p>
                </body>
                </html>
            """)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class WithingsAuthManager:
    """Manages Withings API authentication."""

    def __init__(self, client_id: str, client_secret: str, callback_uri: str,
                 credentials_file: Path):
        """Initialize authentication manager.

        Args:
            client_id: Withings API client ID
            client_secret: Withings API client secret
            callback_uri: OAuth callback URI
            credentials_file: Path to store credentials
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_uri = callback_uri
        self.credentials_file = credentials_file

        # Use new OAuth client
        self.oauth_client = WithingsOAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            callback_uri=callback_uri,
            token_storage_path=credentials_file,
            auto_refresh=True
        )


    def authorize(self) -> OAuthToken:
        """Perform OAuth authorization flow.

        Returns:
            OAuthToken object

        Raises:
            Exception if authorization fails
        """
        # Generate authorization URL
        state = secrets.token_urlsafe(32)
        authorize_url = self.oauth_client.get_authorization_url(state)
        logger.info(f"Authorization URL: {authorize_url}")

        # Log the scopes being requested
        print(f"\nRequesting OAuth scopes: user.info, user.metrics, user.activity, user.sleepevents")
        print(f"Check the URL above to verify these scopes are included.\n")

        # Open browser for user authorization
        print("\n" + "="*70)
        print("IMPORTANT: Withings Authorization")
        print("="*70)
        print("\nYou will be asked to grant permissions for:")
        print("  ✓ user.info       - Basic user information")
        print("  ✓ user.metrics    - Weight, body composition, heart rate")
        print("  ✓ user.activity   - Steps, distance, calories")
        print("  ✓ user.sleepevents - Sleep sessions and quality")
        print("\nPlease make sure to APPROVE ALL permissions when asked!")
        print("="*70)
        print("\nOpening browser for Withings authorization...")
        print(f"If the browser doesn't open, visit this URL:\n{authorize_url}\n")
        webbrowser.open(authorize_url)

        # Parse callback URI to get host and port
        parsed_uri = urlparse(self.callback_uri)
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 8080

        # Start local server to receive callback
        print(f"Waiting for authorization callback on {host}:{port}...")
        server = HTTPServer((host, port), OAuthCallbackHandler)

        # Wait for single request (the callback)
        server.handle_request()

        if not OAuthCallbackHandler.auth_code:
            raise Exception("Failed to receive authorization code")

        # Exchange code for credentials
        print("Exchanging authorization code for credentials...")
        token = self.oauth_client.exchange_code_for_token(OAuthCallbackHandler.auth_code)

        print("Authorization successful!\n")
        return token

    def get_credentials(self, force_refresh: bool = False) -> OAuthToken:
        """Get valid credentials, refreshing if necessary.

        Args:
            force_refresh: Force new authorization even if credentials exist

        Returns:
            Valid credentials

        Raises:
            Exception if authorization required but fails
        """
        # If force refresh, re-authorize
        if force_refresh:
            return self.authorize()

        # Try to get valid token (will auto-refresh if expired)
        try:
            return self.oauth_client.get_valid_token()
        except Exception:
            # Token invalid or missing, need new authorization
            return self.authorize()

    def is_authorized(self) -> bool:
        """Check if valid credentials exist.

        Returns:
            True if authorized, False otherwise
        """
        return self.oauth_client.token is not None

    def clear_credentials(self):
        """Clear stored credentials."""
        if self.credentials_file.exists():
            self.credentials_file.unlink()
            logger.info("Cleared stored credentials")

        self.oauth_client.token = None


def get_auth_manager(client_id: str, client_secret: str, callback_uri: str,
                    credentials_file: Path) -> WithingsAuthManager:
    """Get authentication manager instance.

    Args:
        client_id: Withings API client ID
        client_secret: Withings API client secret
        callback_uri: OAuth callback URI
        credentials_file: Path to credentials file

    Returns:
        WithingsAuthManager instance
    """
    return WithingsAuthManager(client_id, client_secret, callback_uri, credentials_file)
