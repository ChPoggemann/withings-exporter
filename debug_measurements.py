#!/usr/bin/env python3
"""Debug measurements API with different parameters."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from withings_exporter.oauth_client import OAuthToken
from withings_exporter.api_client import WithingsAPIClient

# Load credentials
cred_file = Path.home() / ".withings" / "credentials.json"
with open(cred_file) as f:
    data = json.load(f)

token = OAuthToken.from_dict(data)
api = WithingsAPIClient(access_token=token.access_token)

print("="*70)
print("Testing Measurements API with Different Parameters")
print("="*70)

# Test 1: No parameters at all
print("\n1. No parameters (default)...")
try:
    result = api.get_measurements()
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Only end date
print("\n2. Only enddate (last 7 days)...")
try:
    result = api.get_measurements(enddate=int(datetime.now().timestamp()))
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Specific measure type (weight = 1)
print("\n3. With meastype=1 (WEIGHT)...")
try:
    result = api.get_measurements(meastype=1)
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
    print(f"  meastype=1 is WEIGHT")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Very old start date
print("\n4. From year 2000...")
try:
    result = api.get_measurements(startdate=int(datetime(2000, 1, 1).timestamp()))
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 5: Check what the actual API response contains
print("\n5. Raw API response inspection...")
try:
    result = api.get_measurements()
    print(f"✓ API Response type: {type(result)}")
    print(f"  - Response keys: {list(result.keys())}")
    print(f"  - measuregrps length: {len(result.get('measuregrps', []))}")
    if 'more' in result:
        print(f"  - Has 'more' data: {result['more']}")
    if 'offset' in result:
        print(f"  - Offset: {result['offset']}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 6: Try with category filter
print("\n6. With category=1 (real measurements)...")
try:
    result = api.get_measurements(category=1)
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 7: Try with lastupdate instead of startdate
print("\n7. Using lastupdate (timestamp from 2020)...")
try:
    timestamp = int(datetime(2020, 1, 1).timestamp())
    result = api.get_measurements(lastupdate=timestamp)
    measuregrps = result.get('measuregrps', [])
    print(f"✓ Success: {len(measuregrps)} groups")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "="*70)
