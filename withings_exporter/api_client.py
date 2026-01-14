"""Direct REST API client for Withings API."""

import logging
import time
from datetime import date, datetime
from typing import Callable, List, Optional, Union

import requests

logger = logging.getLogger(__name__)

# API base URLs and endpoints
BASE_URL = "https://wbsapi.withings.net"
MEASURE_ENDPOINT = "/measure"
MEASURE_V2_ENDPOINT = "/v2/measure"
SLEEP_V2_ENDPOINT = "/v2/sleep"
USER_ENDPOINT = "/v2/user"
REQUEST_TIMEOUT = (10, 30)


class WithingsAPIError(Exception):
    """Base exception for Withings API errors."""

    def __init__(self, status_code: int, message: str, response: dict = None):
        """Initialize API error.

        Args:
            status_code: Withings API status code
            message: Error message
            response: Full response dict if available
        """
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"Withings API Error {status_code}: {message}")


class WithingsAuthError(WithingsAPIError):
    """Authentication/authorization errors (401, 2554)."""
    pass


class WithingsRateLimitError(WithingsAPIError):
    """Rate limit exceeded (601)."""

    def __init__(self, retry_after: int = 60):
        """Initialize rate limit error.

        Args:
            retry_after: Seconds to wait before retry
        """
        self.retry_after = retry_after
        super().__init__(601, f"Rate limit exceeded. Retry after {retry_after}s")


class WithingsInvalidParamsError(WithingsAPIError):
    """Invalid parameters."""
    pass


class WithingsAPIClient:
    """Direct REST API client for Withings."""

    # Status code mapping
    STATUS_MESSAGES = {
        0: "Success",
        100: "The hash is missing, invalid, or does not match the provided email",
        247: "User is deactivated",
        286: "No such subscription was found",
        293: "The callback URL is either absent or incorrect",
        294: "No such subscription could be deleted",
        304: "The comment is either absent or incorrect",
        305: "Too many notifications are already set",
        328: "User is unauthorized",
        342: "Signature is wrong",
        343: "Wrong Notification Callback Url",
        601: "Too Many Requests",
        2554: "Unknown action",
        2555: "An unknown error occurred",
    }

    def __init__(
        self,
        access_token: str,
        token_refresh_callback: Optional[Callable] = None
    ):
        """Initialize API client.

        Args:
            access_token: OAuth access token
            token_refresh_callback: Callback function when token needs refresh
        """
        self.access_token = access_token
        self.token_refresh_callback = token_refresh_callback

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        retry_count: int = 0
    ) -> dict:
        """Make HTTP request to Withings API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Query parameters
            data: POST data
            retry_count: Current retry attempt

        Returns:
            Response body dict (unwrapped from Withings envelope)

        Raises:
            WithingsAPIError: On API errors
            WithingsAuthError: On authentication errors
            WithingsRateLimitError: On rate limit errors
        """
        url = f"{BASE_URL}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }

        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            elif method.upper() == 'POST':
                response = requests.post(url, params=params, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            result = response.json()

            # Withings wraps responses in {"status": 0, "body": {...}}
            status = result.get('status', -1)

            if status == 0:
                return result.get('body', {})
            elif status == 401 or status == 328 or status == 2554:
                # Authentication errors
                raise WithingsAuthError(
                    status,
                    self.STATUS_MESSAGES.get(status, "Authentication failed"),
                    result
                )
            elif status == 601:
                # Rate limit error
                if retry_count < 3:
                    wait_time = min(60 * (2 ** retry_count), 300)
                    logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry {retry_count + 1}/3")
                    time.sleep(wait_time)
                    return self._make_request(method, endpoint, params, data, retry_count + 1)
                else:
                    raise WithingsRateLimitError()
            else:
                # Other API errors
                message = self.STATUS_MESSAGES.get(status, f"Unknown error (status {status})")
                raise WithingsAPIError(status, message, result)

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            raise WithingsAPIError(-1, f"HTTP request failed: {e}")

    def get_measurements(
        self,
        startdate: Optional[Union[datetime, int]] = None,
        enddate: Optional[Union[datetime, int]] = None,
        meastype: Optional[int] = None,
        category: int = 1,
        lastupdate: Optional[int] = None,
        offset: Optional[int] = None
    ) -> dict:
        """Get body measurements (weight, body composition, vitals).

        GET /measure?action=getmeas

        Args:
            startdate: Start date as Unix timestamp or datetime
            enddate: End date as Unix timestamp or datetime
            meastype: Measurement type filter (1=weight, 4=height, etc.)
            category: 1=real measurements, 2=user objectives
            lastupdate: Unix timestamp for incremental sync

        Returns:
            Dict with 'measuregrps' list, 'more' bool, 'offset' int
        """
        params = {'action': 'getmeas', 'category': category}

        if startdate:
            params['startdate'] = int(startdate.timestamp()) if isinstance(startdate, datetime) else startdate
        if enddate:
            params['enddate'] = int(enddate.timestamp()) if isinstance(enddate, datetime) else enddate
        if meastype:
            params['meastype'] = meastype
        if lastupdate:
            params['lastupdate'] = lastupdate
        if offset is not None:
            params['offset'] = offset

        logger.debug(f"Fetching measurements with params: {params}")
        return self._make_request('GET', MEASURE_ENDPOINT, params=params)

    def get_activity(
        self,
        startdateymd: Union[datetime, date, str],
        enddateymd: Union[datetime, date, str],
        data_fields: Optional[str] = None
    ) -> dict:
        """Get daily activity data (steps, distance, calories).

        GET /v2/measure?action=getactivity

        Args:
            startdateymd: Start date as YYYY-MM-DD string or date object
            enddateymd: End date as YYYY-MM-DD string or date object
            data_fields: Comma-separated field names (optional)

        Returns:
            Dict with 'activities' list, 'more' bool, 'offset' int
        """
        params = {'action': 'getactivity'}

        # Format dates as YYYY-MM-DD
        if isinstance(startdateymd, (datetime, date)):
            params['startdateymd'] = startdateymd.strftime('%Y-%m-%d')
        else:
            params['startdateymd'] = startdateymd

        if isinstance(enddateymd, (datetime, date)):
            params['enddateymd'] = enddateymd.strftime('%Y-%m-%d')
        else:
            params['enddateymd'] = enddateymd

        if data_fields:
            params['data_fields'] = data_fields

        logger.debug(f"Fetching activity with params: {params}")
        return self._make_request('GET', MEASURE_V2_ENDPOINT, params=params)

    def get_sleep_summary(
        self,
        startdateymd: Union[datetime, date, str],
        enddateymd: Union[datetime, date, str],
        data_fields: Optional[List[str]] = None
    ) -> dict:
        """Get sleep summary data (sleep sessions and quality).

        POST /v2/sleep?action=getsummary

        Args:
            startdateymd: Start date as YYYY-MM-DD string or date object
            enddateymd: End date as YYYY-MM-DD string or date object
            data_fields: List of field names to request

        Returns:
            Dict with 'series' list (sleep sessions), 'more' bool, 'offset' int

        Available data fields:
            - breathing_disturbances_intensity
            - deepsleepduration
            - durationtosleep
            - durationtowakeup
            - hr_average, hr_max, hr_min
            - lightsleepduration
            - remsleepduration
            - rr_average, rr_max, rr_min
            - sleep_score
            - snoring
            - snoringepisodecount
            - wakeupcount
            - wakeupduration
        """
        data = {'action': 'getsummary'}

        # Format dates as YYYY-MM-DD
        if isinstance(startdateymd, (datetime, date)):
            data['startdateymd'] = startdateymd.strftime('%Y-%m-%d')
        else:
            data['startdateymd'] = startdateymd

        if isinstance(enddateymd, (datetime, date)):
            data['enddateymd'] = enddateymd.strftime('%Y-%m-%d')
        else:
            data['enddateymd'] = enddateymd

        if data_fields:
            data['data_fields'] = ','.join(data_fields)

        logger.debug(f"Fetching sleep summary with params: {data}")
        return self._make_request('POST', SLEEP_V2_ENDPOINT, data=data)

    def get_user_devices(self) -> dict:
        """Get user's devices.

        GET /v2/user?action=getdevice

        Returns:
            Dict with 'devices' list
        """
        params = {'action': 'getdevice'}
        logger.debug("Fetching user devices")
        return self._make_request('GET', USER_ENDPOINT, params=params)
