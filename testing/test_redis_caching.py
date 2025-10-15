"""
Tests for Redis caching in Gemini Analysis Service
"""

import pytest
from unittest.mock import Mock, patch
from app.services.gemini_analysis_service import GeminiAnalysisService
from app.cache.redis_client import get_ttl_for_metric


class TestRedisCaching:
    """Test Redis L1 caching functionality"""
    
    @pytest.fixture
    def sample_temperature_data(self):
        """Sample temperature data for testing"""
        return {
            'max_data': [
                {'date': '2024-01-01', 'value': 28.5},
                {'date': '2024-01-02', 'value': 29.1},
                {'date': '2024-01-03', 'value': 27.8}
            ],
            'min_data': [
                {'date': '2024-01-01', 'value': 18.2},
                {'date': '2024-01-02', 'value': 19.0},
                {'date': '2024-01-03', 'value': 17.5}
            ]
        }
    
    def test_build_cache_key(self):
        """Test cache key format"""
        service = GeminiAnalysisService()
        cache_key = service._build_cache_key(
            "Albion Park", 
            "temperature", 
            "abc123def456" * 5  # 60 char hash
        )
        
        assert cache_key.startswith("ai:analysis:")
        assert "Albion Park" in cache_key
        assert "temperature" in cache_key
        assert "abc123def456" in cache_key
    
    def test_ttl_configuration(self):
        """Test TTL values for different metrics"""
        assert get_ttl_for_metric('temperature') == 86400  # 24 hours
        assert get_ttl_for_metric('humidity') == 43200     # 12 hours
        assert get_ttl_for_metric('wind') == 7200          # 2 hours
        assert get_ttl_for_metric('unknown') == 3600       # 1 hour default
    
    @patch('app.cache.redis_client.Redis')
    def test_redis_get_hit(self, mock_redis_class):
        """Test Redis cache hit"""
        # Setup mock Redis
        mock_redis = Mock()
        mock_redis.get.return_value = "Cached analysis text"
        mock_redis_class.from_url.return_value = mock_redis
        
        with patch('app.cache.redis_client.get_redis', return_value=mock_redis):
            service = GeminiAnalysisService()
            service.redis = mock_redis
            service.use_redis = True
            
            result = service._get_from_redis("test:key")
            
            assert result == "Cached analysis text"
            mock_redis.get.assert_called_once_with("test:key")
            mock_redis.incr.assert_called_once_with("test:key:hits")
    
    @patch('app.cache.redis_client.Redis')
    def test_redis_get_miss(self, mock_redis_class):
        """Test Redis cache miss"""
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis_class.from_url.return_value = mock_redis
        
        with patch('app.cache.redis_client.get_redis', return_value=mock_redis):
            service = GeminiAnalysisService()
            service.redis = mock_redis
            service.use_redis = True
            
            result = service._get_from_redis("test:key")
            
            assert result is None
            mock_redis.get.assert_called_once_with("test:key")
            mock_redis.incr.assert_not_called()
    
    @patch('app.cache.redis_client.Redis')
    def test_redis_save(self, mock_redis_class):
        """Test saving to Redis with TTL"""
        mock_redis = Mock()
        mock_redis_class.from_url.return_value = mock_redis
        
        with patch('app.cache.redis_client.get_redis', return_value=mock_redis):
            service = GeminiAnalysisService()
            service.redis = mock_redis
            service.use_redis = True
            
            result = service._save_to_redis(
                "test:key", 
                "Analysis text", 
                "temperature"
            )
            
            assert result is True
            mock_redis.setex.assert_called_once_with(
                "test:key", 
                86400,  # TTL for temperature
                "Analysis text"
            )
    
    @patch('app.cache.redis_client.Redis')
    def test_redis_unavailable_fallback(self, mock_redis_class):
        """Test graceful fallback when Redis is unavailable"""
        with patch('app.cache.redis_client.get_redis', return_value=None):
            service = GeminiAnalysisService()
            service.redis = None
            service.use_redis = False
            
            # Should return None without errors
            result = service._get_from_redis("test:key")
            assert result is None
            
            # Should return False without errors
            result = service._save_to_redis("test:key", "text", "temperature")
            assert result is False
    
    def test_data_hash_consistency(self, sample_temperature_data):
        """Test that same data produces same hash"""
        service = GeminiAnalysisService()
        
        hash1 = service._generate_data_hash(sample_temperature_data)
        hash2 = service._generate_data_hash(sample_temperature_data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters
    
    def test_data_hash_different_for_different_data(self, sample_temperature_data):
        """Test that different data produces different hash"""
        service = GeminiAnalysisService()
        
        data2 = sample_temperature_data.copy()
        data2['max_data'] = [{'date': '2024-01-01', 'value': 30.0}]
        
        hash1 = service._generate_data_hash(sample_temperature_data)
        hash2 = service._generate_data_hash(data2)
        
        assert hash1 != hash2


class TestCacheIntegration:
    """Integration tests for L1+L2 cache layers"""
    
    @patch('app.cache.redis_client.Redis')
    @patch('app.services.gemini_analysis_service.Session')
    def test_cache_hierarchy_redis_hit(self, mock_session, mock_redis_class):
        """Test that Redis is checked before database"""
        # Setup Redis mock (cache hit)
        mock_redis = Mock()
        mock_redis.get.return_value = "Redis cached analysis"
        
        # Setup DB mock (should not be called)
        mock_db = Mock()
        
        with patch('app.cache.redis_client.get_redis', return_value=mock_redis):
            service = GeminiAnalysisService()
            service.redis = mock_redis
            service.use_redis = True
            
            result = service._get_cached_analysis(
                mock_db, 
                "Test Station", 
                "temperature",
                None, None, 
                "abc123"
            )
            
            assert result == "Redis cached analysis"
            # Database should not be queried
            mock_db.query.assert_not_called()
    
    @patch('app.cache.redis_client.Redis')
    def test_cache_hierarchy_db_hit_populates_redis(self, mock_redis_class):
        """Test that DB hit populates Redis for future requests"""
        # Setup Redis mock (cache miss initially)
        mock_redis = Mock()
        mock_redis.get.return_value = None
        
        # Setup DB mock (cache hit)
        from datetime import datetime
        mock_cached = Mock()
        mock_cached.analysis_text = "Database cached analysis"
        mock_cached.access_count = 5
        
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cached
        
        with patch('app.cache.redis_client.get_redis', return_value=mock_redis):
            with patch('app.database.models.WeatherAnalysisCache'):
                service = GeminiAnalysisService()
                service.redis = mock_redis
                service.use_redis = True
                
                from datetime import date
                result = service._get_cached_analysis(
                    mock_db,
                    "Test Station",
                    "temperature",
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    "abc123"
                )
                
                assert result == "Database cached analysis"
                # Redis should be populated
                mock_redis.setex.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
