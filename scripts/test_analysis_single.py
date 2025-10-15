"""
Simple tester: POST a single analysis request and measure response time.
Usage: python scripts/test_analysis_single.py
"""
import time
import json
import os
import requests

API = os.getenv('API_BASE', 'http://127.0.0.1:8000')

payload = {
    "metric": "temperature",
    "data": {"values": [22, 23, 21, 24, 25], "timestamps": ["2025-10-01","2025-10-02","2025-10-03","2025-10-04","2025-10-05"]},
    "station_name": "TEST STATION",
    "date_range": "2025-10-01_to_2025-10-05"
}

def main():
    url = f"{API}/api/analysis/generate"
    headers = {"Content-Type": "application/json"}
    print('Posting to', url)
    t0 = time.time()
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    elapsed = time.time() - t0
    print('Status:', r.status_code)
    try:
        print('JSON:', json.dumps(r.json(), indent=2))
    except Exception:
        print('Text:', r.text[:1000])
    print('Elapsed: %.3fs' % elapsed)

if __name__ == '__main__':
    main()
