"""
Gemini AI Analysis Service
Generates weather insights using Google's Gemini API with database caching
"""

import os
import hashlib
import google.generativeai as genai
from typing import Dict, Any, Optional
from datetime import datetime, date
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_


class GeminiAnalysisService:
    """Service for generating weather analysis using Gemini API with caching"""
    
    def __init__(self):
        """Initialize Gemini service with API key from environment"""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Using gemini-1.5-flash for faster, cost-effective responses
            # Alternative models: 'gemini-pro', 'gemini-1.5-pro', 'gemini-2.0-flash-exp'
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
            self.model_name = 'gemini-2.5-flash-lite'
        else:
            self.model = None
            self.model_name = None
    
    def is_configured(self) -> bool:
        """Check if Gemini API is properly configured"""
        return self.api_key is not None and self.model is not None
    
    def _generate_data_hash(self, data: Dict[str, Any]) -> str:
        """
        Generate a hash of the data to identify unique datasets
        
        Args:
            data: The weather data dictionary
            
        Returns:
            SHA256 hash of the data
        """
        # Create a stable string representation of the data
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
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
        Retrieve cached analysis from database
        
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
                
                print(f"✓ Cache hit for {station_name} - {metric} (accessed {cached.access_count} times)")
                return cached.analysis_text
            
            return None
            
        except Exception as e:
            print(f"Error retrieving cached analysis: {str(e)}")
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
        Save generated analysis to database cache
        
        Args:
            db: Database session
            station_name: Name of weather station
            metric: Metric type
            start_date: Start date of data range
            end_date: End date of data range
            data_hash: Hash of the data
            analysis: Generated analysis text
            
        Returns:
            True if saved successfully, False otherwise
        """
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
            
            print(f"✓ Cached new analysis for {station_name} - {metric}")
            return True
            
        except Exception as e:
            print(f"Error saving to cache: {str(e)}")
            db.rollback()
            return False
    
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
