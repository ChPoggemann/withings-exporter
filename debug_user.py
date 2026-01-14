#!/usr/bin/env python3
"""Check which user the API is authenticated as."""

import json
from pathlib import Path
from datetime import datetime, timedelta

from withings_exporter.oauth_client import OAuthToken
from withings_exporter.api_client import WithingsAPIClient

# Load credentials
cred_file = Path.home() / ".withings" / "credentials.json"
with open(cred_file) as f:
    data = json.load(f)

token = OAuthToken.from_dict(data)
api = WithingsAPIClient(access_token=token.access_token)

print("="*70)
print("User Identity Check")
print("="*70)

print(f"\nAuthenticated User ID: {data.get('userid')}")
print(f"Access Token (first 10 chars): {data['access_token'][:10]}...")

# Try to get user devices and see what user they belong to
print("\n--- Devices ---")
try:
    result = api.get_user_devices()
    devices = result.get('devices', [])
    print(f"Found {len(devices)} devices:")
    for device in devices:
        print(f"  - {device.get('model')} ({device.get('type')})")
        print(f"    Device ID: {device.get('deviceid')}")
        print(f"    Battery: {device.get('battery')}")
        if 'userid' in device:
            print(f"    User ID: {device['userid']}")
except Exception as e:
    print(f"Error: {e}")

# Try to get activity to see if it shows a user ID
print("\n--- Recent Activity (should work) ---")
try:
    result = api.get_activity(
        startdateymd=datetime.now() - timedelta(days=7),
        enddateymd=datetime.now()
    )
    activities = result.get('activities', [])
    if activities:
        print(f"Found {len(activities)} activity records")
        activity = activities[0]
        print(f"Sample activity keys: {list(activity.keys())}")
        if 'userid' in activity:
            print(f"Activity User ID: {activity['userid']}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
print("If the devices and activity show a DIFFERENT user ID than")
print("the authenticated user ID above, that's the problem!")
print("="*70)
