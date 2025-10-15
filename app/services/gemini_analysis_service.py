"""
Gemini AI Analysis Service
Generates weather insights using Google's Gemini API with L1 (Redis) + L2 (Database) caching
"""

import os
import hashlib
import google.generativeai as genai
from typing import Dict, Any, Optional
from datetime import datetime, date
import json
import time
import threading
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.cache.redis_client import get_redis, get_ttl_for_metric


class RateLimiter:
    """Token bucket rate limiter for API calls"""
    
    def __init__(self, max_requests: int = 10, time_window: float = 1.0):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """
        Acquire a token to make a request
        
        Args:
            timeout: Maximum time to wait for a token (seconds)
            
        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                # Refill tokens based on elapsed time
                elapsed = now - self.last_update
                self.tokens = min(
                    self.max_requests,
                    self.tokens + (elapsed / self.time_window) * self.max_requests
                )
                self.last_update = now
                
                # Try to consume a token
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True
            
            # Check timeout
            if time.time() - start_time >= timeout:
                return False
            
            # Wait a bit before retrying
            time.sleep(0.05)


class GeminiAnalysisService:
    """Service for generating weather analysis using Gemini API with L1/L2 caching"""
    
    def __init__(self):
        """Initialize Gemini service with API key from environment"""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Using gemini-2.5-flash-lite for faster, cost-effective responses
            # Alternative models: 'gemini-pro', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
            self.model_name = 'gemini-2.5-flash-lite'
        else:
            self.model = None
            self.model_name = None
        
        # Initialize Redis client
        self.redis = get_redis()
        self.use_redis = self.redis is not None
        
        # Initialize rate limiter (10 requests per second by default)
        # Adjust based on your Gemini API tier limits
        rate_limit = int(os.getenv('GEMINI_RATE_LIMIT', '10'))
        self.rate_limiter = RateLimiter(max_requests=rate_limit, time_window=1.0)
        
        # Cache statistics (in-memory tracking)
        self.stats = {
            'redis_hits': 0,
            'redis_misses': 0,
            'db_hits': 0,
            'db_misses': 0,
            'generations': 0
        }
    
    def is_configured(self) -> bool:
        """Check if Gemini API is properly configured"""
        return self.api_key is not None and self.model is not None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.stats['redis_hits'] + self.stats['redis_misses']
        redis_hit_rate = (self.stats['redis_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        total_db_requests = self.stats['db_hits'] + self.stats['db_misses']
        db_hit_rate = (self.stats['db_hits'] / total_db_requests * 100) if total_db_requests > 0 else 0
        
        return {
            'redis': {
                'hits': self.stats['redis_hits'],
                'misses': self.stats['redis_misses'],
                'hit_rate': f"{redis_hit_rate:.1f}%"
            },
            'database': {
                'hits': self.stats['db_hits'],
                'misses': self.stats['db_misses'],
                'hit_rate': f"{db_hit_rate:.1f}%"
            },
            'generations': self.stats['generations'],
            'total_requests': total_requests
        }
    
    def _generate_data_hash(self, data: Dict[str, Any]) -> str:
        """
        Generate a deterministic hash of the data to identify unique datasets
        
        Args:
            data: The weather data dictionary
            
        Returns:
            SHA256 hash of the data
        """
        # Normalize the data structure to ensure consistency
        # Extract only the essential data values, ignoring metadata like labels, colors, etc.
        normalized_data = {}
        
        # For temperature data
        if 'max_data' in data or 'min_data' in data:
            max_values = []
            min_values = []
            dates = []
            
            if 'max_data' in data and isinstance(data['max_data'], list):
                for item in data['max_data']:
                    if isinstance(item, dict):
                        max_values.append(item.get('value'))
                        dates.append(item.get('date'))
                    
            if 'min_data' in data and isinstance(data['min_data'], list):
                for item in data['min_data']:
                    if isinstance(item, dict):
                        min_values.append(item.get('value'))
                        
            normalized_data = {
                'max_values': sorted([v for v in max_values if v is not None]),
                'min_values': sorted([v for v in min_values if v is not None]),
                'dates': sorted([d for d in dates if d is not None])
            }
        
        # For wind/humidity data (simpler structure)
        elif 'values' in data:
            values = data.get('values', [])
            timestamps = data.get('timestamps', [])
            normalized_data = {
                'values': sorted([v for v in values if v is not None]),
                'timestamps': sorted([t for t in timestamps if t is not None])
            }
        
        # For other data structures, use the full data
        else:
            normalized_data = data
        
        # Create a stable string representation
        data_str = json.dumps(normalized_data, sort_keys=True)
        hash_value = hashlib.sha256(data_str.encode()).hexdigest()
        
        # Debug logging (can be removed in production)
        print(f"🔍 Data hash: {hash_value[:12]} for normalized: {str(normalized_data)[:100]}...")
        
        return hash_value
    
    def _build_cache_key(self, station_name: str, metric: str, data_hash: str) -> str:
        """
        Build Redis cache key
        
        Args:
            station_name: Name of weather station
            metric: Metric type
            data_hash: SHA256 hash of data
            
        Returns:
            Cache key string
        """
        # Format: ai:analysis:{station}:{metric}:{hash_prefix}
        hash_prefix = data_hash[:12]  # Use first 12 chars for readability
        return f"ai:analysis:{station_name}:{metric}:{hash_prefix}"
    
    def _get_from_redis(self, cache_key: str) -> Optional[str]:
        """
        Get analysis from Redis (L1 cache) with optimized performance
        
        Args:
            cache_key: Redis key
            
        Returns:
            Cached analysis or None
        """
        if not self.use_redis:
            return None
        
        try:
            # Use pipeline for atomic operations (faster than individual commands)
            pipe = self.redis.pipeline()
            pipe.get(cache_key)
            pipe.incr(f"{cache_key}:hits")
            results = pipe.execute()
            
            cached = results[0]
            if cached:
                self.stats['redis_hits'] += 1
                print(f"✓ Redis L1 cache HIT: {cache_key} (hits: {results[1]})")
                return cached
            else:
                self.stats['redis_misses'] += 1
                print(f"⚠️  Redis L1 cache MISS: {cache_key}")
            return None
        except Exception as e:
            print(f"⚠️  Redis get error: {str(e)}")
            return None
    
    def _save_to_redis(self, cache_key: str, analysis: str, metric: str) -> bool:
        """
        Save analysis to Redis (L1 cache) with TTL
        
        Args:
            cache_key: Redis key
            analysis: Analysis text
            metric: Metric type for TTL selection
            
        Returns:
            True if saved successfully
        """
        if not self.use_redis:
            return False
        
        try:
            ttl = get_ttl_for_metric(metric)
            self.redis.setex(cache_key, ttl, analysis)
            print(f"✓ Saved to Redis L1 cache (TTL={ttl}s): {cache_key}")
            return True
        except Exception as e:
            print(f"⚠️  Redis save error: {str(e)}")
            return False
    
    def _get_cached_analysis(
        self,
        db: Session,
        station_name: str,
        metric: str,
        start_date: date,
        end_date: date,
        data_hash: str
    ) -> Optional[str]:
        """
        Retrieve cached analysis from L1 (Redis) then L2 (Database)
        
        Args:
            db: Database session
            station_name: Name of weather station
            metric: Metric type ('temperature', 'wind', 'humidity')
            start_date: Start date of data range
            end_date: End date of data range
            data_hash: Hash of the data
            
        Returns:
            Cached analysis text or None if not found
        """
        # L1: Check Redis cache first (fast)
        cache_key = self._build_cache_key(station_name, metric, data_hash)
        redis_result = self._get_from_redis(cache_key)
        if redis_result:
            return redis_result
        
        # L2: Check database cache (slower but durable)
        try:
            from app.database.models import WeatherAnalysisCache
            
            # Look for exact match
            cached = db.query(WeatherAnalysisCache).filter(
                and_(
                    WeatherAnalysisCache.station_name == station_name,
                    WeatherAnalysisCache.metric_type == metric,
                    WeatherAnalysisCache.data_hash == data_hash,
                    WeatherAnalysisCache.is_valid == True
                )
            ).first()
            
            if cached:
                # Update access statistics
                cached.access_count += 1
                cached.last_accessed = datetime.utcnow()
                db.commit()
                
                self.stats['db_hits'] += 1
                print(f"✓ Database L2 cache HIT for {station_name} - {metric} (accessed {cached.access_count} times)")
                
                # Populate Redis cache for future fast access
                self._save_to_redis(cache_key, cached.analysis_text, metric)
                
                return cached.analysis_text
            
            self.stats['db_misses'] += 1
            return None
            
        except Exception as e:
            print(f"Error retrieving cached analysis from DB: {str(e)}")
            return None
    
    def _save_to_cache(
        self,
        db: Session,
        station_name: str,
        metric: str,
        start_date: date,
        end_date: date,
        data_hash: str,
        analysis: str
    ) -> bool:
        """
        Save generated analysis to both L1 (Redis) and L2 (Database) cache
        
        Args:
            db: Database session
            station_name: Name of weather station
            metric: Metric type
            start_date: Start date of data range
            end_date: End date of data range
            data_hash: Hash of the data
            analysis: Generated analysis text
            
        Returns:
            True if saved successfully to at least one cache
        """
        success = False
        
        # Save to Redis (L1) with TTL
        cache_key = self._build_cache_key(station_name, metric, data_hash)
        if self._save_to_redis(cache_key, analysis, metric):
            success = True
        
        # Save to Database (L2) for durability and analytics
        try:
            from app.database.models import WeatherAnalysisCache
            
            # Create new cache entry
            cache_entry = WeatherAnalysisCache(
                station_name=station_name,
                metric_type=metric,
                start_date=start_date,
                end_date=end_date,
                data_hash=data_hash,
                analysis_text=analysis,
                model_used=self.model_name,
                generated_at=datetime.utcnow(),
                access_count=1,
                last_accessed=datetime.utcnow(),
                is_valid=True
            )
            
            db.add(cache_entry)
            db.commit()
            
            print(f"✓ Saved to Database L2 cache for {station_name} - {metric}")
            success = True
            
        except Exception as e:
            print(f"Error saving to database cache: {str(e)}")
            db.rollback()
        
        return success
    
    async def generate_temperature_analysis(
        self, 
        data: Dict[str, Any],
        station_name: str,
        date_range: Optional[str] = None,
        db: Session = None
    ) -> str:
        """
        Generate temperature analysis based on chart data with caching
        
        Args:
            data: Temperature data including max and min values
            station_name: Name of the weather station
            date_range: Optional date range string
            db: Database session for caching (optional)
            
        Returns:
            Generated analysis text
        """
        if not self.is_configured():
            return self._fallback_temperature_analysis(data)
        
        # Generate data hash for caching
        data_hash = self._generate_data_hash(data)
        
        # Extract date range from data if not provided
        start_date = None
        end_date = None
        if data.get('max_data') and len(data['max_data']) > 0:
            try:
                dates = [d['date'] for d in data['max_data'] if d.get('date')]
                if dates:
                    start_date = datetime.strptime(min(dates), '%Y-%m-%d').date()
                    end_date = datetime.strptime(max(dates), '%Y-%m-%d').date()
            except Exception as e:
                print(f"Error parsing dates: {e}")
        
        # Try to get from cache if database session provided
        if db and start_date and end_date:
            cached_analysis = self._get_cached_analysis(
                db, station_name, 'temperature', start_date, end_date, data_hash
            )
            if cached_analysis:
                return cached_analysis
        
        try:
            # Prepare statistics
            stats = self._calculate_temp_stats(data)
            
            prompt = f"""You are a meteorological analyst. Analyze the following temperature data from {station_name}{' for ' + date_range if date_range else ''}.

Temperature Statistics:
- Average Maximum Temperature: {stats['avg_max']:.1f}°C
- Average Minimum Temperature: {stats['avg_min']:.1f}°C
- Highest Maximum: {stats['max_temp']:.1f}°C
- Lowest Minimum: {stats['min_temp']:.1f}°C
- Temperature Range: {stats['range']:.1f}°C
- Number of Data Points: {stats['count']}

Provide a concise, 2-3 sentence analysis focusing on:
1. Overall temperature pattern and trend
2. Notable variations or extremes
3. What this means for the local weather conditions

Keep the tone professional but accessible. Do not use markdown formatting."""

            # Apply rate limiting before API call
            if not self.rate_limiter.acquire(timeout=30.0):
                raise Exception("Rate limit timeout: Could not acquire token for Gemini API call")
            
            # Track generation for statistics
            self.stats['generations'] += 1
            
            response = self.model.generate_content(prompt)
            analysis = response.text.strip()
            
            # Save to cache if database session provided
            if db and start_date and end_date:
                self._save_to_cache(
                    db, station_name, 'temperature', start_date, end_date, data_hash, analysis
                )
            
            return analysis
            
        except Exception as e:
            print(f"Error generating Gemini analysis: {str(e)}")
            return self._fallback_temperature_analysis(data)
    
    async def generate_wind_analysis(
        self, 
        data: Dict[str, Any],
        station_name: str,
        date_range: Optional[str] = None,
        db: Session = None
    ) -> str:
        """
        Generate wind speed analysis based on chart data with caching
        
        Args:
            data: Wind speed data
            station_name: Name of the weather station
            date_range: Optional date range string
            db: Database session for caching (optional)
            
        Returns:
            Generated analysis text
        """
        if not self.is_configured():
            return self._fallback_wind_analysis(data)
        
        # Generate data hash for caching
        data_hash = self._generate_data_hash(data)
        
        # Extract date range from data
        start_date = None
        end_date = None
        if data.get('data') and len(data['data']) > 0:
            try:
                dates = [d['date'] for d in data['data'] if d.get('date')]
                if dates:
                    start_date = datetime.strptime(min(dates), '%Y-%m-%d').date()
                    end_date = datetime.strptime(max(dates), '%Y-%m-%d').date()
            except Exception as e:
                print(f"Error parsing dates: {e}")
        
        # Try to get from cache
        if db and start_date and end_date:
            cached_analysis = self._get_cached_analysis(
                db, station_name, 'wind', start_date, end_date, data_hash
            )
            if cached_analysis:
                return cached_analysis
        
        try:
            stats = self._calculate_wind_stats(data)
            
            prompt = f"""You are a meteorological analyst. Analyze the following wind speed data from {station_name}{' for ' + date_range if date_range else ''}.

Wind Speed Statistics:
- Average Wind Speed: {stats['avg_speed']:.1f} km/h
- Maximum Wind Speed: {stats['max_speed']:.1f} km/h
- Minimum Wind Speed: {stats['min_speed']:.1f} km/h
- Number of Data Points: {stats['count']}

Provide a concise, 2-3 sentence analysis focusing on:
1. Overall wind patterns and intensity
2. Implications for local weather and outdoor activities
3. Any notable patterns or trends

Keep the tone professional but accessible. Do not use markdown formatting."""

            # Apply rate limiting before API call (for wind analysis)
            if not self.rate_limiter.acquire(timeout=30.0):
                raise Exception("Rate limit timeout: Could not acquire token for Gemini API call")
            
            # Track generation for statistics
            self.stats['generations'] += 1
            
            response = self.model.generate_content(prompt)
            analysis = response.text.strip()
            
            # Save to cache
            if db and start_date and end_date:
                self._save_to_cache(
                    db, station_name, 'wind', start_date, end_date, data_hash, analysis
                )
            
            return analysis
            
        except Exception as e:
            print(f"Error generating Gemini analysis: {str(e)}")
            return self._fallback_wind_analysis(data)
    
    async def generate_humidity_analysis(
        self, 
        data: Dict[str, Any],
        station_name: str,
        date_range: Optional[str] = None,
        db: Session = None
    ) -> str:
        """
        Generate humidity analysis based on chart data with caching
        
        Args:
            data: Humidity data
            station_name: Name of the weather station
            date_range: Optional date range string
            db: Database session for caching (optional)
            
        Returns:
            Generated analysis text
        """
        if not self.is_configured():
            return self._fallback_humidity_analysis(data)
        
        # Generate data hash for caching
        data_hash = self._generate_data_hash(data)
        
        # Extract date range from data
        start_date = None
        end_date = None
        if data.get('data') and len(data['data']) > 0:
            try:
                dates = [d['date'] for d in data['data'] if d.get('date')]
                if dates:
                    start_date = datetime.strptime(min(dates), '%Y-%m-%d').date()
                    end_date = datetime.strptime(max(dates), '%Y-%m-%d').date()
            except Exception as e:
                print(f"Error parsing dates: {e}")
        
        # Try to get from cache
        if db and start_date and end_date:
            cached_analysis = self._get_cached_analysis(
                db, station_name, 'humidity', start_date, end_date, data_hash
            )
            if cached_analysis:
                return cached_analysis
        
        try:
            stats = self._calculate_humidity_stats(data)
            
            prompt = f"""You are a meteorological analyst. Analyze the following humidity data from {station_name}{' for ' + date_range if date_range else ''}.

Humidity Statistics:
- Average Humidity: {stats['avg_humidity']:.1f}%
- Maximum Humidity: {stats['max_humidity']:.1f}%
- Minimum Humidity: {stats['min_humidity']:.1f}%
- Number of Data Points: {stats['count']}

Provide a concise, 2-3 sentence analysis focusing on:
1. Overall humidity levels and patterns
2. What this means for comfort and weather conditions
3. Any notable trends or variations

Keep the tone professional but accessible. Do not use markdown formatting."""

            # Apply rate limiting before API call (for humidity analysis)
            if not self.rate_limiter.acquire(timeout=30.0):
                raise Exception("Rate limit timeout: Could not acquire token for Gemini API call")
            
            # Track generation for statistics
            self.stats['generations'] += 1
            
            response = self.model.generate_content(prompt)
            analysis = response.text.strip()
            
            # Save to cache
            if db and start_date and end_date:
                self._save_to_cache(
                    db, station_name, 'humidity', start_date, end_date, data_hash, analysis
                )
            
            return analysis
            
        except Exception as e:
            print(f"Error generating Gemini analysis: {str(e)}")
            return self._fallback_humidity_analysis(data)
    
    def _calculate_temp_stats(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate temperature statistics"""
        max_temps = [d['value'] for d in data.get('max_data', []) if d.get('value') is not None]
        min_temps = [d['value'] for d in data.get('min_data', []) if d.get('value') is not None]
        
        if not max_temps or not min_temps:
            return {
                'avg_max': 0, 'avg_min': 0, 'max_temp': 0, 
                'min_temp': 0, 'range': 0, 'count': 0
            }
        
        avg_max = sum(max_temps) / len(max_temps)
        avg_min = sum(min_temps) / len(min_temps)
        
        return {
            'avg_max': avg_max,
            'avg_min': avg_min,
            'max_temp': max(max_temps),
            'min_temp': min(min_temps),
            'range': max(max_temps) - min(min_temps),
            'count': len(max_temps)
        }
    
    def _calculate_wind_stats(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate wind speed statistics (converting m/s to km/h)"""
        wind_speeds = [d['value'] * 3.6 for d in data.get('data', []) if d.get('value') is not None]
        
        if not wind_speeds:
            return {'avg_speed': 0, 'max_speed': 0, 'min_speed': 0, 'count': 0}
        
        return {
            'avg_speed': sum(wind_speeds) / len(wind_speeds),
            'max_speed': max(wind_speeds),
            'min_speed': min(wind_speeds),
            'count': len(wind_speeds)
        }
    
    def _calculate_humidity_stats(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate humidity statistics"""
        humidity_values = [d['value'] for d in data.get('data', []) if d.get('value') is not None]
        
        if not humidity_values:
            return {'avg_humidity': 0, 'max_humidity': 0, 'min_humidity': 0, 'count': 0}
        
        return {
            'avg_humidity': sum(humidity_values) / len(humidity_values),
            'max_humidity': max(humidity_values),
            'min_humidity': min(humidity_values),
            'count': len(humidity_values)
        }
    
    def _fallback_temperature_analysis(self, data: Dict[str, Any]) -> str:
        """Fallback analysis when Gemini is not available"""
        stats = self._calculate_temp_stats(data)
        if stats['count'] == 0:
            return "Insufficient temperature data available for analysis."
        
        return (f"Temperature data shows an average maximum of {stats['avg_max']:.1f}°C "
                f"and minimum of {stats['avg_min']:.1f}°C. The temperature range of "
                f"{stats['range']:.1f}°C indicates {'significant' if stats['range'] > 15 else 'moderate'} "
                f"daily variations across the monitoring period.")
    
    def _fallback_wind_analysis(self, data: Dict[str, Any]) -> str:
        """Fallback analysis when Gemini is not available"""
        stats = self._calculate_wind_stats(data)
        if stats['count'] == 0:
            return "Insufficient wind speed data available for analysis."
        
        return (f"Wind speed averages {stats['avg_speed']:.1f} km/h with peaks up to "
                f"{stats['max_speed']:.1f} km/h. This indicates "
                f"{'strong' if stats['avg_speed'] > 25 else 'moderate' if stats['avg_speed'] > 15 else 'light'} "
                f"wind conditions during the monitoring period.")
    
    def _fallback_humidity_analysis(self, data: Dict[str, Any]) -> str:
        """Fallback analysis when Gemini is not available"""
        stats = self._calculate_humidity_stats(data)
        if stats['count'] == 0:
            return "Insufficient humidity data available for analysis."
        
        return (f"Humidity levels average {stats['avg_humidity']:.1f}%, ranging from "
                f"{stats['min_humidity']:.1f}% to {stats['max_humidity']:.1f}%. "
                f"These conditions suggest a {'humid' if stats['avg_humidity'] > 70 else 'comfortable' if stats['avg_humidity'] > 40 else 'dry'} "
                f"environment during the monitoring period.")


# Global service instance
gemini_service = GeminiAnalysisService()
