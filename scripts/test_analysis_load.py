"""
Simple concurrent load tester: send N parallel POST requests and measure response times and errors.
Usage: python scripts/test_analysis_load.py
"""
import time
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

API = os.getenv('API_BASE', 'http://127.0.0.1:8000')

payload_template = {
    "metric": "temperature",
    "data": {"values": [22, 23, 21, 24, 25], "timestamps": ["2025-10-01","2025-10-02","2025-10-03","2025-10-04","2025-10-05"]},
    "station_name": "LOAD_TEST_STATION",
    "date_range": "2025-10-01_to_2025-10-05"
}

def call_one(i):
    url = f"{API}/api/analysis/generate"
    headers = {"Content-Type": "application/json"}
    payload = payload_template.copy()
    # vary the station slightly to simulate different requests
    payload['station_name'] = f"LOAD_TEST_STATION_{i % 10}"
    t0 = time.time()
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        elapsed = time.time() - t0
        return (i, r.status_code, elapsed, r.text[:200])
    except Exception as e:
        return (i, 'ERR', 999.0, str(e))

def main():
    N = 50
    print(f'Starting load test: {N} parallel requests')
    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(call_one, i) for i in range(N)]
        for fut in as_completed(futures):
            results.append(fut.result())

    successes = [r for r in results if r[1] == 200]
    errors = [r for r in results if r[1] != 200]
    times = [r[2] for r in successes]
    print(f'Total: {len(results)}, Success: {len(successes)}, Errors: {len(errors)}')
    if times:
        print('Min: %.3fs, Max: %.3fs, Avg: %.3fs' % (min(times), max(times), sum(times)/len(times)))
    if errors:
        print('Sample errors:', errors[:5])

if __name__ == '__main__':
    main()
