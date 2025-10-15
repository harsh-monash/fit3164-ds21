"""
Quick optimization validation test
Tests the improved cache performance with before/after comparison
"""
import time
import json
import requests
import os

API = os.getenv('API_BASE', 'http://127.0.0.1:8000')

# Test payload with consistent data (matches real frontend structure)
payload = {
    "metric": "temperature",
    "data": {
        "max_data": [
            {"date": "2025-10-01", "value": 29.2, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-02", "value": 30.1, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-03", "value": 28.5, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-04", "value": 31.0, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-05", "value": 29.8, "station_name": "OPTIMIZATION_TEST_STATION"}
        ],
        "min_data": [
            {"date": "2025-10-01", "value": 18.5, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-02", "value": 19.2, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-03", "value": 17.8, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-04", "value": 20.1, "station_name": "OPTIMIZATION_TEST_STATION"},
            {"date": "2025-10-05", "value": 18.9, "station_name": "OPTIMIZATION_TEST_STATION"}
        ]
    },
    "station_name": "OPTIMIZATION_TEST_STATION",
    "date_range": "2025-10-01_to_2025-10-05"
}

def call_api(payload):
    """Call the API and measure time"""
    url = f"{API}/api/analysis/generate"
    headers = {"Content-Type": "application/json"}
    t0 = time.time()
    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        elapsed = time.time() - t0
        return r.status_code == 200, elapsed
    except Exception as e:
        return False, -1

def get_stats():
    """Get cache statistics"""
    try:
        r = requests.get(f"{API}/api/analysis/stats", timeout=5)
        if r.status_code == 200:
            return r.json().get('statistics', {})
    except Exception:
        pass
    return None

def main():
    print("="*80)
    print("CACHE OPTIMIZATION VALIDATION TEST")
    print("="*80)
    
    print("\n[STEP 1] Check server status...")
    try:
        r = requests.get(f"{API}/api/analysis/status", timeout=5)
        if r.status_code != 200 or not r.json().get('gemini_configured'):
            print("❌ Server not available or Gemini not configured!")
            return
        print("✅ Server is running")
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return
    
    print("\n[STEP 2] First request (cold cache)...")
    success1, time1 = call_api(payload)
    if success1:
        print(f"✅ Request 1: {time1:.3f}s (cold cache - should be ~6-7s)")
    else:
        print("❌ Request 1 failed")
        return
    
    print("\n[STEP 3] Second request (should hit cache)...")
    time.sleep(0.5)  # Let cache propagate
    success2, time2 = call_api(payload)
    if success2:
        print(f"✅ Request 2: {time2:.3f}s (warm cache)")
        speedup = time1 / time2 if time2 > 0 else 0
        print(f"   Speedup: {speedup:.1f}x faster")
        
        if time2 < 0.5:
            print("   ✅ OPTIMIZATION WORKING! Cache hit < 500ms")
        elif time2 < 1.0:
            print("   ⚠️  Improved but still slow (500ms - 1s)")
        else:
            print("   ❌ Still not hitting cache effectively (> 1s)")
    else:
        print("❌ Request 2 failed")
        return
    
    print("\n[STEP 4] Check cache statistics...")
    stats = get_stats()
    if stats:
        print(f"   Redis hits: {stats['redis']['hits']}")
        print(f"   Redis misses: {stats['redis']['misses']}")
        print(f"   Redis hit rate: {stats['redis']['hit_rate']}")
        print(f"   DB hits: {stats['database']['hits']}")
        print(f"   DB misses: {stats['database']['misses']}")
        print(f"   DB hit rate: {stats['database']['hit_rate']}")
        print(f"   Generations: {stats['generations']}")
        print(f"   Total requests: {stats['total_requests']}")
        
        if stats['redis']['hits'] > 0:
            print("   ✅ Redis cache is working!")
        else:
            print("   ⚠️  No Redis hits yet - may need more requests")
    else:
        print("   ⚠️  Statistics endpoint not available")
    
    print("\n[STEP 5] Multiple requests to same station...")
    print("   Running 10 requests to test cache consistency...")
    times = []
    for i in range(10):
        success, elapsed = call_api(payload)
        if success:
            times.append(elapsed)
    
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        print(f"   Min: {min_time:.3f}s, Max: {max_time:.3f}s, Avg: {avg_time:.3f}s")
        
        cache_hits = len([t for t in times if t < 0.5])
        cache_hit_ratio = cache_hits / len(times) * 100
        print(f"   Cache hits (<500ms): {cache_hits}/10 ({cache_hit_ratio:.0f}%)")
        
        if cache_hit_ratio >= 80:
            print("   ✅ EXCELLENT: >80% cache hit ratio!")
        elif cache_hit_ratio >= 50:
            print("   ⚠️  GOOD: 50-80% cache hit ratio")
        else:
            print("   ❌ POOR: <50% cache hit ratio - needs investigation")
    
    print("\n[FINAL STATS]")
    final_stats = get_stats()
    if final_stats:
        print(f"   Total Redis hits: {final_stats['redis']['hits']}")
        print(f"   Total Redis hit rate: {final_stats['redis']['hit_rate']}")
        print(f"   Total generations: {final_stats['generations']}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
