"""
Redis Client for Fast L1 Caching
Provides singleton Redis connection for weather analysis caching
"""

import os
from typing import Optional
from redis import Redis, ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError


class RedisClient:
    """Singleton Redis client with connection pooling"""
    
    _instance: Optional[Redis] = None
    _pool: Optional[ConnectionPool] = None
    
    @classmethod
    def get_client(cls) -> Optional[Redis]:
        """
        Get Redis client instance (singleton)
        
        Returns:
            Redis client or None if not configured
        """
        if cls._instance is None:
            redis_url = os.getenv('REDIS_URL')
            if not redis_url:
                print("⚠️  REDIS_URL not set - Redis caching disabled")
                return None
            
            try:
                # Create connection pool for efficiency
                cls._pool = ConnectionPool.from_url(
                    redis_url,
                    decode_responses=True,
                    max_connections=10,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                cls._instance = Redis(connection_pool=cls._pool)
                
                # Test connection
                cls._instance.ping()
                print(f"✓ Redis connected: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
                
            except (ConnectionError, TimeoutError) as e:
                print(f"⚠️  Redis connection failed: {str(e)} - caching disabled")
                cls._instance = None
                cls._pool = None
        
        return cls._instance
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Redis is available"""
        client = cls.get_client()
        if client is None:
            return False
        
        try:
            client.ping()
            return True
        except Exception:
            return False
    
    @classmethod
    def close(cls):
        """Close Redis connection and pool"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None


# Convenience function for getting Redis client
def get_redis() -> Optional[Redis]:
    """Get Redis client instance"""
    return RedisClient.get_client()


# TTL (Time To Live) configuration for different metrics
# Values in seconds
TTL_CONFIG = {
    'temperature': 86400,    # 24 hours - data changes slowly
    'humidity': 43200,       # 12 hours - moderate change rate
    'wind': 7200,            # 2 hours - changes frequently
    'default': 3600          # 1 hour - fallback
}


def get_ttl_for_metric(metric: str) -> int:
    """
    Get TTL (seconds) for a given metric type
    
    Args:
        metric: Metric type ('temperature', 'wind', 'humidity')
        
    Returns:
        TTL in seconds
    """
    return TTL_CONFIG.get(metric.lower(), TTL_CONFIG['default'])
