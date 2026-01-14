#!/usr/bin/env python3
"""Call Withings REST API directly to see raw responses."""

import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

# Load credentials
cred_file = Path.home() / ".withings" / "credentials.json"
with open(cred_file) as f:
    data = json.load(f)

access_token = data['access_token']

# Withings API base URLs
MEASURE_URL = "https://wbsapi.withings.net/measure"
MEASURE_V2_URL = "https://wbsapi.withings.net/v2/measure"
SLEEP_URL = "https://wbsapi.withings.net/v2/sleep"

headers = {
    "Authorization": f"Bearer {access_token}"
}

print("="*70)
print("Withings RAW REST API Test")
print("="*70)
print(f"\nUsing Access Token: {access_token[:20]}...")
print()

# Test 1: Get measurements (raw)
print("1. RAW Measure - Getmeas (NO parameters)")
print("-" * 70)
try:
    response = requests.get(
        MEASURE_URL,
        headers=headers,
        params={
            "action": "getmeas"
        }
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)

# Test 2: Get measurements with date range
print("2. RAW Measure - Getmeas (with startdate from 2020)")
print("-" * 70)
try:
    startdate_ts = int(datetime(2020, 1, 1).timestamp())
    response = requests.get(
        MEASURE_URL,
        headers=headers,
        params={
            "action": "getmeas",
            "startdate": startdate_ts
        }
    )
    print(f"Status Code: {response.status_code}")
    print(f"Request URL: {response.url}")
    print(f"Response Body:")
    resp_data = response.json()
    print(json.dumps(resp_data, indent=2))

    if resp_data.get('status') == 0:
        print(f"\n✓ API returned status 0 (success)")
        print(f"  Measuregrps: {len(resp_data.get('body', {}).get('measuregrps', []))}")
    else:
        print(f"\n✗ API returned status: {resp_data.get('status')}")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)

# Test 3: Get sleep summary (raw)
print("3. RAW Sleep - Getsummary (from 2020)")
print("-" * 70)
try:
    startdate = "2020-01-01"
    enddate = datetime.now().strftime("%Y-%m-%d")

    response = requests.post(
        SLEEP_URL,
        headers=headers,
        params={
            "action": "getsummary"
        },
        data={
            "startdateymd": startdate,
            "enddateymd": enddate,
            "data_fields": "breathing_disturbances_intensity,deepsleepduration,durationtosleep,durationtowakeup,hr_average,hr_max,hr_min,lightsleepduration,remsleepduration,rr_average,rr_max,rr_min,sleep_score,snoring,snoringepisodecount,wakeupcount,wakeupduration"
        }
    )
    print(f"Status Code: {response.status_code}")
    print(f"Request URL: {response.url}")
    print(f"Response Body:")
    resp_data = response.json()
    print(json.dumps(resp_data, indent=2))

    if resp_data.get('status') == 0:
        print(f"\n✓ API returned status 0 (success)")
        print(f"  Sleep series: {len(resp_data.get('body', {}).get('series', []))}")
    else:
        print(f"\n✗ API returned status: {resp_data.get('status')}")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)

# Test 4: Get activity (raw - this one WORKS for you)
print("4. RAW Measure - Getactivity (last 7 days)")
print("-" * 70)
try:
    startdate = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    enddate = datetime.now().strftime("%Y-%m-%d")

    response = requests.get(
        MEASURE_V2_URL,
        headers=headers,
        params={
            "action": "getactivity",
            "startdateymd": startdate,
            "enddateymd": enddate
        }
    )
    print(f"Status Code: {response.status_code}")
    print(f"Request URL: {response.url}")
    print(f"Response Body (truncated):")
    resp_data = response.json()

    # Truncate activities for readability
    if 'body' in resp_data and 'activities' in resp_data['body']:
        activities = resp_data['body']['activities']
        resp_data['body']['activities'] = activities[:2] + [f"... ({len(activities)} total)"] if len(activities) > 2 else activities

    print(json.dumps(resp_data, indent=2))

    if resp_data.get('status') == 0:
        print(f"\n✓ API returned status 0 (success)")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)

# Test 5: Check if there are different versions or modes
print("5. Test with different API versions/parameters for measurements")
print("-" * 70)

# Try v2 endpoint
print("\nTrying V2 endpoint...")
try:
    response = requests.get(
        MEASURE_V2_URL,
        headers=headers,
        params={
            "action": "getmeas"
        }
    )
    print(f"V2 Status Code: {response.status_code}")
    print(f"V2 Response: {json.dumps(response.json(), indent=2)[:500]}...")
except Exception as e:
    print(f"V2 Error: {e}")

# Try with category parameter
print("\nTrying with category=1 (real measurements)...")
try:
    response = requests.get(
        MEASURE_URL,
        headers=headers,
        params={
            "action": "getmeas",
            "category": 1
        }
    )
    print(f"Category Status Code: {response.status_code}")
    print(f"Category Response: {json.dumps(response.json(), indent=2)[:500]}...")
except Exception as e:
    print(f"Category Error: {e}")

print("\n" + "="*70)
print("RAW API test complete!")
print("\nLook for:")
print("  - Any 'error' or 'message' fields in responses")
print("  - Status codes other than 0 (0 = success in Withings API)")
print("  - Differences between working (activity) and non-working (measure/sleep)")
print("="*70)
