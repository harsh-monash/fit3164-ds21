"""
Comprehensive Use Case Testing Suite
Runs all test scenarios and generates a detailed markdown report
"""
import time
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import subprocess

API = os.getenv('API_BASE', 'http://127.0.0.1:8000')

# Test configuration
REAL_STATION = "ADELAIDE AIRPORT"

# Temperature payload (uses max_data and min_data)
TEST_PAYLOAD_REAL = {
    "metric": "temperature",
    "data": {
        "max_data": [
            {"date": "2025-10-01", "value": 29.2, "station_name": REAL_STATION},
            {"date": "2025-10-02", "value": 30.1, "station_name": REAL_STATION},
            {"date": "2025-10-03", "value": 28.5, "station_name": REAL_STATION},
            {"date": "2025-10-04", "value": 31.0, "station_name": REAL_STATION},
            {"date": "2025-10-05", "value": 29.8, "station_name": REAL_STATION},
            {"date": "2025-10-06", "value": 28.7, "station_name": REAL_STATION},
            {"date": "2025-10-07", "value": 30.3, "station_name": REAL_STATION}
        ],
        "min_data": [
            {"date": "2025-10-01", "value": 18.5, "station_name": REAL_STATION},
            {"date": "2025-10-02", "value": 19.2, "station_name": REAL_STATION},
            {"date": "2025-10-03", "value": 17.8, "station_name": REAL_STATION},
            {"date": "2025-10-04", "value": 20.1, "station_name": REAL_STATION},
            {"date": "2025-10-05", "value": 18.9, "station_name": REAL_STATION},
            {"date": "2025-10-06", "value": 17.5, "station_name": REAL_STATION},
            {"date": "2025-10-07", "value": 19.8, "station_name": REAL_STATION}
        ]
    },
    "station_name": REAL_STATION,
    "date_range": "2025-10-01_to_2025-10-07"
}

# Wind payload (uses data array)
TEST_PAYLOAD_WIND = {
    "metric": "wind",
    "data": {
        "data": [
            {"date": "2025-10-01", "value": 12.5, "station_name": REAL_STATION},
            {"date": "2025-10-02", "value": 15.3, "station_name": REAL_STATION},
            {"date": "2025-10-03", "value": 10.8, "station_name": REAL_STATION},
            {"date": "2025-10-04", "value": 18.2, "station_name": REAL_STATION},
            {"date": "2025-10-05", "value": 14.6, "station_name": REAL_STATION},
            {"date": "2025-10-06", "value": 11.9, "station_name": REAL_STATION},
            {"date": "2025-10-07", "value": 16.4, "station_name": REAL_STATION}
        ]
    },
    "station_name": REAL_STATION,
    "date_range": "2025-10-01_to_2025-10-07"
}

# Humidity payload (uses data array)
TEST_PAYLOAD_HUMIDITY = {
    "metric": "humidity",
    "data": {
        "data": [
            {"date": "2025-10-01", "value": 65.0, "station_name": REAL_STATION},
            {"date": "2025-10-02", "value": 72.3, "station_name": REAL_STATION},
            {"date": "2025-10-03", "value": 58.7, "station_name": REAL_STATION},
            {"date": "2025-10-04", "value": 80.1, "station_name": REAL_STATION},
            {"date": "2025-10-05", "value": 68.5, "station_name": REAL_STATION},
            {"date": "2025-10-06", "value": 62.4, "station_name": REAL_STATION},
            {"date": "2025-10-07", "value": 75.8, "station_name": REAL_STATION}
        ]
    },
    "station_name": REAL_STATION,
    "date_range": "2025-10-01_to_2025-10-07"
}

class TestReport:
    """Collect and format test results"""
    
    def __init__(self):
        self.sections = []
        self.start_time = datetime.now()
        
    def add_section(self, title, content):
        self.sections.append({"title": title, "content": content})
    
    def generate_markdown(self):
        """Generate final markdown report"""
        md = f"""# Weather Analysis System - Use Case Test Report

**Test Date:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**Test Duration:** {(datetime.now() - self.start_time).total_seconds():.2f} seconds

---

## Executive Summary

This report documents comprehensive testing of the Weather Analysis System against defined use cases:
- **Use Case 1:** AI-Enhanced Weather Analysis (single user, cache behavior)
- **Use Case 2:** System Performance Under Load (50+ concurrent users)

---

"""
        for section in self.sections:
            md += f"## {section['title']}\n\n{section['content']}\n\n---\n\n"
        
        return md

def check_server_status():
    """Check if server is running and configured"""
    try:
        r = requests.get(f"{API}/api/analysis/status", timeout=5)
        return r.status_code == 200 and r.json().get('gemini_configured', False)
    except Exception as e:
        return False

def create_payload_with_station(base_payload, station_name):
    """Create a new payload with updated station name in all data fields"""
    import copy
    payload = copy.deepcopy(base_payload)
    payload['station_name'] = station_name
    
    # Update station_name in data arrays
    if 'max_data' in payload['data']:
        for item in payload['data']['max_data']:
            item['station_name'] = station_name
        for item in payload['data']['min_data']:
            item['station_name'] = station_name
    elif 'data' in payload['data']:
        for item in payload['data']['data']:
            item['station_name'] = station_name
    
    return payload

def get_redis_keys():
    """Get Redis cache keys"""
    try:
        result = subprocess.run(
            ['docker', 'exec', 'weather_redis', 'redis-cli', '--raw', 'KEYS', 'ai:analysis:*'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            keys = [k for k in result.stdout.strip().split('\n') if k]
            return keys
        return []
    except Exception as e:
        print(f"Error getting Redis keys: {e}")
        return []

def get_redis_key_ttl(key):
    """Get TTL for a Redis key in seconds"""
    try:
        result = subprocess.run(
            ['docker', 'exec', 'weather_redis', 'redis-cli', 'TTL', key],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
        return -1
    except Exception:
        return -1

def call_analysis_api(payload, timeout=30):
    """Make a single API call and measure timing"""
    url = f"{API}/api/analysis/generate"
    headers = {"Content-Type": "application/json"}
    
    t0 = time.time()
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        elapsed = time.time() - t0
        return {
            'status': r.status_code,
            'elapsed': elapsed,
            'success': r.status_code == 200,
            'response': r.json() if r.status_code == 200 else None,
            'error': None
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            'status': 'ERROR',
            'elapsed': elapsed,
            'success': False,
            'response': None,
            'error': str(e)
        }

def test_single_request_cold(report):
    """Test Case 1: Single request with cold cache"""
    print("\n[TEST 1] Single Request - Cold Cache")
    
    # Clear any existing cache for this station
    print("  Clearing Redis cache for test station...")
    try:
        subprocess.run(
            ['docker', 'exec', 'weather_redis', 'redis-cli', 'DEL', f'ai:analysis:{REAL_STATION}:temperature:*'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass
    
    # Make request
    print("  Making API request...")
    result = call_analysis_api(TEST_PAYLOAD_REAL)
    
    # Collect results
    content = f"""### Test Scenario
- **Goal:** Verify AI analysis generation from cold cache
- **Station:** {REAL_STATION}
- **Metric:** Temperature
- **Cache State:** Cold (no existing cache)

### Results
- **Status:** {'✅ PASS' if result['success'] else '❌ FAIL'}
- **Response Time:** {result['elapsed']:.3f}s
- **HTTP Status:** {result['status']}
- **Analysis Generated:** {'Yes' if result.get('response', {}).get('analysis') else 'No'}

### Analysis Response
```
{result.get('response', {}).get('analysis', 'N/A')[:500]}...
```

### Acceptance Criteria
- ✅ Response time < 5s: {'PASS' if result['elapsed'] < 5.0 else 'FAIL'}
- ✅ HTTP 200 status: {'PASS' if result['status'] == 200 else 'FAIL'}
- ✅ Analysis text returned: {'PASS' if result.get('response', {}).get('analysis') else 'FAIL'}
- ✅ Gemini configured: {'PASS' if result.get('response', {}).get('gemini_configured') else 'FAIL'}
"""
    
    report.add_section("Test 1: Single Request (Cold Cache)", content)
    return result

def test_single_request_warm(report, previous_result):
    """Test Case 2: Single request with warm cache"""
    print("\n[TEST 2] Single Request - Warm Cache")
    
    # Wait a moment for cache to propagate
    time.sleep(0.5)
    
    # Check Redis keys
    keys_before = get_redis_keys()
    print(f"  Redis keys before: {len(keys_before)}")
    
    # Make same request again
    print("  Making API request (should hit cache)...")
    result = call_analysis_api(TEST_PAYLOAD_REAL)
    
    # Check if this was a cache hit (should be much faster)
    is_cache_hit = result['elapsed'] < 0.5  # Cache hits should be <500ms
    
    content = f"""### Test Scenario
- **Goal:** Verify Redis L1 cache hit performance
- **Station:** {REAL_STATION}
- **Metric:** Temperature
- **Cache State:** Warm (previous request cached)

### Results
- **Status:** {'✅ PASS' if result['success'] and is_cache_hit else '❌ FAIL'}
- **Response Time:** {result['elapsed']:.3f}s
- **HTTP Status:** {result['status']}
- **Cache Hit:** {'✅ Yes (< 500ms)' if is_cache_hit else '❌ No (> 500ms)'}
- **Redis Keys:** {len(keys_before)} keys found

### Performance Comparison
- **Cold Cache (Test 1):** {previous_result['elapsed']:.3f}s
- **Warm Cache (Test 2):** {result['elapsed']:.3f}s
- **Speedup:** {previous_result['elapsed'] / result['elapsed'] if result['elapsed'] > 0 else 0:.1f}x faster

### Acceptance Criteria
- ✅ Response time < 100ms: {'PASS' if result['elapsed'] < 0.1 else 'FAIL'}
- ✅ HTTP 200 status: {'PASS' if result['status'] == 200 else 'FAIL'}
- ✅ Faster than cold cache: {'PASS' if result['elapsed'] < previous_result['elapsed'] else 'FAIL'}
- ✅ Cache hit achieved: {'PASS' if is_cache_hit else 'FAIL'}
"""
    
    report.add_section("Test 2: Single Request (Warm Cache)", content)
    return result

def test_concurrent_load_warm(report, n_requests=50):
    """Test Case 3: Concurrent load with warm cache"""
    print(f"\n[TEST 3] Concurrent Load - Warm Cache ({n_requests} requests)")
    
    def call_one(i):
        return call_analysis_api(TEST_PAYLOAD_REAL, timeout=60)
    
    print(f"  Launching {n_requests} parallel requests...")
    results = []
    t_start = time.time()
    
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(call_one, i) for i in range(n_requests)]
        for fut in as_completed(futures):
            results.append(fut.result())
    
    t_total = time.time() - t_start
    
    # Analyze results
    successes = [r for r in results if r['success']]
    errors = [r for r in results if not r['success']]
    times = [r['elapsed'] for r in successes]
    
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    avg_time = sum(times) / len(times) if times else 0
    median_time = sorted(times)[len(times)//2] if times else 0
    
    # Calculate percentiles
    p95 = sorted(times)[int(len(times)*0.95)] if times else 0
    p99 = sorted(times)[int(len(times)*0.99)] if times else 0
    
    # Check if most requests were cache hits (< 1s)
    cache_hits = len([t for t in times if t < 1.0])
    cache_hit_ratio = cache_hits / len(times) if times else 0
    
    content = f"""### Test Scenario
- **Goal:** Validate system performance under concurrent load with warm cache
- **Requests:** {n_requests} parallel requests
- **Station:** {REAL_STATION} (same for all requests)
- **Cache State:** Warm (cached from previous tests)

### Results
- **Status:** {'✅ PASS' if len(successes) >= n_requests * 0.95 else '❌ FAIL'}
- **Total Duration:** {t_total:.3f}s
- **Successful Requests:** {len(successes)}/{n_requests} ({len(successes)/n_requests*100:.1f}%)
- **Failed Requests:** {len(errors)}
- **Cache Hit Ratio:** {cache_hit_ratio*100:.1f}% ({cache_hits}/{len(times)} < 1s)

### Performance Metrics
| Metric | Value |
|--------|-------|
| Min Response Time | {min_time:.3f}s |
| Max Response Time | {max_time:.3f}s |
| Avg Response Time | {avg_time:.3f}s |
| Median Response Time | {median_time:.3f}s |
| 95th Percentile | {p95:.3f}s |
| 99th Percentile | {p99:.3f}s |

### Acceptance Criteria
- ✅ Success rate > 95%: {'PASS' if len(successes) >= n_requests * 0.95 else 'FAIL'}
- ✅ Avg response time < 1s: {'PASS' if avg_time < 1.0 else 'FAIL'}
- ✅ Max response time < 5s: {'PASS' if max_time < 5.0 else 'FAIL'}
- ✅ Cache hit ratio > 80%: {'PASS' if cache_hit_ratio > 0.8 else 'FAIL'}

### Error Details
{f"{len(errors)} errors occurred" if errors else "No errors"}
"""
    
    report.add_section("Test 3: Concurrent Load (Warm Cache)", content)
    return results

def test_concurrent_load_cold(report, n_requests=50):
    """Test Case 4: Concurrent load with varied stations (cold cache)"""
    print(f"\n[TEST 4] Concurrent Load - Cold Cache ({n_requests} requests, varied stations)")
    
    stations = [
        f"LOAD_TEST_STATION_{i % 10}" for i in range(n_requests)
    ]
    
    def call_one(i):
        payload = create_payload_with_station(TEST_PAYLOAD_REAL, stations[i])
        return call_analysis_api(payload, timeout=60)
    
    print(f"  Launching {n_requests} parallel requests (10 unique stations)...")
    results = []
    t_start = time.time()
    
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = [ex.submit(call_one, i) for i in range(n_requests)]
        for fut in as_completed(futures):
            results.append(fut.result())
    
    t_total = time.time() - t_start
    
    # Analyze results
    successes = [r for r in results if r['success']]
    errors = [r for r in results if not r['success']]
    times = [r['elapsed'] for r in successes]
    
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    avg_time = sum(times) / len(times) if times else 0
    median_time = sorted(times)[len(times)//2] if times else 0
    
    # Calculate percentiles
    p95 = sorted(times)[int(len(times)*0.95)] if times else 0
    p99 = sorted(times)[int(len(times)*0.99)] if times else 0
    
    content = f"""### Test Scenario
- **Goal:** Test system under concurrent load with cache misses (varied stations)
- **Requests:** {n_requests} parallel requests
- **Stations:** 10 unique stations (simulating different users)
- **Cache State:** Cold (new stations, cache misses expected)

### Results
- **Status:** {'✅ PASS' if len(successes) >= n_requests * 0.9 else '❌ FAIL'}
- **Total Duration:** {t_total:.3f}s
- **Successful Requests:** {len(successes)}/{n_requests} ({len(successes)/n_requests*100:.1f}%)
- **Failed Requests:** {len(errors)}

### Performance Metrics
| Metric | Value |
|--------|-------|
| Min Response Time | {min_time:.3f}s |
| Max Response Time | {max_time:.3f}s |
| Avg Response Time | {avg_time:.3f}s |
| Median Response Time | {median_time:.3f}s |
| 95th Percentile | {p95:.3f}s |
| 99th Percentile | {p99:.3f}s |

### Rate Limiting Effectiveness
- **Rate Limiter:** 10 requests/second configured
- **Expected Min Duration:** {n_requests / 10:.1f}s (if fully rate-limited)
- **Actual Duration:** {t_total:.3f}s
- **Rate Limiting Active:** {'Yes - requests were queued' if t_total > (n_requests / 10) * 0.8 else 'Minimal queuing observed'}

### Acceptance Criteria
- ✅ Success rate > 90%: {'PASS' if len(successes) >= n_requests * 0.9 else 'FAIL'}
- ✅ Avg response time < 10s: {'PASS' if avg_time < 10.0 else 'FAIL'}
- ✅ Max response time < 30s: {'PASS' if max_time < 30.0 else 'FAIL'}
- ✅ No timeouts: {'PASS' if len(errors) == 0 else 'FAIL'}

### Error Details
{json.dumps([{'error': e['error'][:100]} for e in errors[:5]], indent=2) if errors else "No errors"}
"""
    
    report.add_section("Test 4: Concurrent Load (Cold Cache)", content)
    return results

def test_cache_effectiveness(report):
    """Test Case 5: Cache effectiveness and TTL verification"""
    print("\n[TEST 5] Cache Effectiveness")
    
    keys = get_redis_keys()
    
    key_details = []
    for key in keys[:10]:  # Sample first 10 keys
        ttl = get_redis_key_ttl(key)
        key_details.append({
            'key': key,
            'ttl': ttl,
            'ttl_formatted': f"{ttl // 3600}h {(ttl % 3600) // 60}m" if ttl > 0 else "Expired" if ttl == -2 else "No expiry"
        })
    
    content = f"""### Test Scenario
- **Goal:** Verify cache is populated and TTL is configured correctly

### Redis Cache Status
- **Total Keys:** {len(keys)}
- **Sample Keys Inspected:** {min(10, len(keys))}

### Key Details (Sample)
| Key | TTL | Status |
|-----|-----|--------|
"""
    
    for kd in key_details:
        content += f"| `{kd['key'][:50]}...` | {kd['ttl_formatted']} | {'✅ Active' if kd['ttl'] > 0 else '❌ Expired'} |\n"
    
    content += f"""

### TTL Configuration Verification
- **Temperature:** Expected 24h (86400s)
- **Humidity:** Expected 12h (43200s)
- **Wind:** Expected 2h (7200s)

### Acceptance Criteria
- ✅ Cache keys exist: {'PASS' if len(keys) > 0 else 'FAIL'}
- ✅ TTLs configured: {'PASS' if any(kd['ttl'] > 0 for kd in key_details) else 'FAIL'}
- ✅ Keys use correct format: {'PASS' if all('ai:analysis:' in kd['key'] for kd in key_details) else 'FAIL'}
"""
    
    report.add_section("Test 5: Cache Effectiveness", content)

def test_functional_requirements(report):
    """Test Case 6: Functional requirements validation"""
    print("\n[TEST 6] Functional Requirements")
    
    # Test different metrics with their proper payloads
    test_configs = [
        ('temperature', TEST_PAYLOAD_REAL),
        ('wind', TEST_PAYLOAD_WIND),
        ('humidity', TEST_PAYLOAD_HUMIDITY)
    ]
    metric_results = []
    
    for metric, payload in test_configs:
        result = call_analysis_api(payload)
        metric_results.append({
            'metric': metric,
            'success': result['success'],
            'elapsed': result['elapsed']
        })
    
    content = f"""### Test Scenario
- **Goal:** Verify all analysis types (temperature, wind, humidity) work correctly

### Results by Metric
| Metric | Status | Response Time | Result |
|--------|--------|---------------|--------|
"""
    
    for mr in metric_results:
        content += f"| {mr['metric'].capitalize()} | {mr['success']} | {mr['elapsed']:.3f}s | {'✅ PASS' if mr['success'] else '❌ FAIL'} |\n"
    
    all_pass = all(mr['success'] for mr in metric_results)
    
    content += f"""

### Acceptance Criteria
- ✅ All metrics supported: {'PASS' if all_pass else 'FAIL'}
- ✅ Temperature analysis: {'PASS' if metric_results[0]['success'] else 'FAIL'}
- ✅ Wind analysis: {'PASS' if metric_results[1]['success'] else 'FAIL'}
- ✅ Humidity analysis: {'PASS' if metric_results[2]['success'] else 'FAIL'}
"""
    
    report.add_section("Test 6: Functional Requirements", content)

def main():
    """Run all tests and generate report"""
    print("=" * 80)
    print("WEATHER ANALYSIS SYSTEM - COMPREHENSIVE USE CASE TESTING")
    print("=" * 80)
    
    # Initialize report
    report = TestReport()
    
    # Pre-flight check
    print("\n[PRE-FLIGHT] Checking server status...")
    if not check_server_status():
        print("❌ Server not available or Gemini not configured!")
        print("   Please ensure server is running: uvicorn app.main:app --reload")
        return
    print("✅ Server is running and Gemini is configured")
    
    # Run tests
    try:
        # Test 1: Single request (cold cache)
        result1 = test_single_request_cold(report)
        
        # Test 2: Single request (warm cache)
        result2 = test_single_request_warm(report, result1)
        
        # Test 3: Concurrent load (warm cache)
        test_concurrent_load_warm(report, n_requests=50)
        
        # Test 4: Concurrent load (cold cache)
        test_concurrent_load_cold(report, n_requests=50)
        
        # Test 5: Cache effectiveness
        test_cache_effectiveness(report)
        
        # Test 6: Functional requirements
        test_functional_requirements(report)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    # Generate report
    print("\n" + "=" * 80)
    print("GENERATING REPORT...")
    print("=" * 80)
    
    markdown = report.generate_markdown()
    
    # Add final summary
    markdown += """## Final Assessment

### Overall System Status
"""
    
    # Save report
    report_path = "docs/USE_CASE_TEST_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"\n✅ Report saved to: {report_path}")
    print(f"   Open in VS Code or your browser to review detailed results")
    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
