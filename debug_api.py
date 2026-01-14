#!/usr/bin/env python3
"""Debug script to test Withings API calls directly."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from withings_exporter.oauth_client import OAuthToken
from withings_exporter.api_client import WithingsAPIClient

# Load credentials
cred_file = Path.home() / ".withings" / "credentials.json"
with open(cred_file) as f:
    data = json.load(f)

# Create OAuth token
token = OAuthToken.from_dict(data)

# Create API client
api = WithingsAPIClient(access_token=token.access_token)

print("="*70)
print("Withings API Debug Test")
print("="*70)

# Test 1: Get user info
print("\n1. Testing user info...")
try:
    user_info = api.get_user_devices()
    devices = user_info.get('devices', [])
    print(f"✓ User info retrieved: {len(devices)} devices found")
    for device in devices:
        print(f"  - {device.get('model')}: {device.get('type')}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Get measurements
print("\n2. Testing measurements (last 30 days)...")
try:
    start_date = datetime.now() - timedelta(days=30)
    result = api.get_measurements(startdate=int(start_date.timestamp()))
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Measurements API call successful")
    print(f"  - Measurement groups returned: {len(measuregrps)}")
    if measuregrps:
        print(f"  - First measurement date: {datetime.fromtimestamp(measuregrps[0]['date'])}")
        print(f"  - Total measures in first group: {len(measuregrps[0].get('measures', []))}")
    else:
        print(f"  ⚠ No measurement data in last 30 days")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2b: Get measurements (ALL TIME - no date filter)
print("\n2b. Testing measurements (ALL TIME)...")
try:
    result = api.get_measurements()
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Measurements API call successful")
    print(f"  - Measurement groups returned: {len(measuregrps)}")
    if measuregrps:
        print(f"  - First measurement date: {datetime.fromtimestamp(measuregrps[0]['date'])}")
        print(f"  - Last measurement date: {datetime.fromtimestamp(measuregrps[-1]['date'])}")
        print(f"  - Sample measure types:")
        for measure in measuregrps[0].get('measures', [])[:5]:
            print(f"    - Type {measure['type']}: {measure['value']} * 10^{measure['unit']}")
    else:
        print(f"  ⚠ NO MEASUREMENT DATA AT ALL in your account!")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2c: Try specific date range from 2016
print("\n2c. Testing measurements (from 2016-09-01)...")
try:
    start_date = datetime(2016, 9, 1)
    result = api.get_measurements(startdate=int(start_date.timestamp()))
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Measurements API call successful")
    print(f"  - Measurement groups returned: {len(measuregrps)}")
    if measuregrps:
        print(f"  - First measurement date: {datetime.fromtimestamp(measuregrps[0]['date'])}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Get sleep summary
print("\n3. Testing sleep data (last 30 days)...")
try:
    start_date = datetime.now() - timedelta(days=30)
    result = api.get_sleep_summary(
        startdateymd=start_date,
        enddateymd=datetime.now(),
        data_fields=['sleep_score', 'deepsleepduration']
    )
    series = result.get('series', [])
    print(f"✓ Sleep API call successful")
    print(f"  - Sleep sessions returned: {len(series)}")
    if series:
        print(f"  - First session date: {datetime.fromtimestamp(series[0]['startdate'])}")
    else:
        print(f"  ⚠ No sleep data in last 30 days")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3b: Get sleep data from 2016
print("\n3b. Testing sleep data (from 2016-09-01)...")
try:
    start_date = datetime(2016, 9, 1)
    result = api.get_sleep_summary(
        startdateymd=start_date,
        enddateymd=datetime.now(),
        data_fields=['sleep_score', 'deepsleepduration', 'remsleepduration']
    )
    series = result.get('series', [])
    print(f"✓ Sleep API call successful")
    print(f"  - Sleep sessions returned: {len(series)}")
    if series:
        print(f"  - First session: {datetime.fromtimestamp(series[0]['startdate'])}")
        print(f"  - Last session: {datetime.fromtimestamp(series[-1]['startdate'])}")
    else:
        print(f"  ⚠ NO SLEEP DATA AT ALL in your account!")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Get activity
print("\n4. Testing activity data (last 7 days)...")
try:
    start_date = datetime.now() - timedelta(days=7)
    result = api.get_activity(
        startdateymd=start_date,
        enddateymd=datetime.now()
    )
    activities = result.get('activities', [])
    print(f"✓ Activity API call successful")
    print(f"  - Activity records returned: {len(activities)}")
    if activities:
        print(f"  - First activity date: {activities[0].get('date')}")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*70)
print("Debug test complete!")
print("="*70)
