from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database.connection import get_db, SessionLocal
from app.database.models import BOMWeatherStation, BOMWeatherData, BOMDataIngestionLog, WeatherStation, WeatherData, Feedback
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import requests
from geoalchemy2 import WKTElement

router = APIRouter()


# Simple proxy endpoint for current weather (uses server-side API key)
@router.get('/weather')
def proxy_current_weather(lat: float, lon: float):
    """Proxy current weather from OpenWeatherMap using server-side API key.
    Query params: lat, lon
    """
    # Try OpenWeatherMap if configured
    owm_key = os.getenv('OWM_API_KEY')
    if owm_key:
        try:
            params = {'lat': lat, 'lon': lon, 'units': 'metric', 'appid': owm_key}
            resp = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                data['_provider'] = 'openweathermap'
            return data
        except requests.RequestException:
            pass

    # Final fallback: Open-Meteo (no API key required)
    try:
        resp = requests.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true', timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data['_provider'] = 'open-meteo'
        return data
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f'Error fetching weather from providers: {str(e)}')


# Public config endpoint for frontend configuration
@router.get('/config')
def get_public_config():
    """Return public configuration values the frontend may need.
    This endpoint intentionally only exposes non-sensitive, client-safe values.
    """
    return {
        'configured': True,
        'providers': ['openweathermap', 'open-meteo']
    }


# --- Ingest current weather for a user-selected location --------------------
class WeatherIngestRequest(BaseModel):
    name: Optional[str] = None
    latitude: float
    longitude: float
    provider: Optional[str] = 'auto'  # 'openweathermap', 'open-meteo'


@router.post('/weather/ingest')
def ingest_weather_for_location(payload: WeatherIngestRequest, db: Session = Depends(get_db)):
    """Fetch current weather for a lat/lon, create or update a station, and persist a WeatherData row.
    Uses OpenWeatherMap if OWM_API_KEY is configured; otherwise falls back to Open-Meteo (no key required).
    """
    lat = float(payload.latitude)
    lon = float(payload.longitude)

    # 1) Try to find an existing station within 1km
    try:
        nearby = db.execute(text("""
            SELECT id FROM weather_stations
            WHERE ST_DWithin(
                location::geography,
                ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
                :radius_m
            )
            LIMIT 1
        """), {"lat": lat, "lon": lon, "radius_m": 1000}).fetchone()
    except Exception:
        nearby = None

    station = None
    if nearby and nearby[0]:
        station = db.query(WeatherStation).get(nearby[0])

    # 2) If not found, create a new WeatherStation
    if not station:
        code = f"USR_{int(datetime.utcnow().timestamp())}"
        station_name = payload.name or f"User Location {code}"
        point = WKTElement(f'POINT({lon} {lat})', srid=4326)
        station = WeatherStation(
            name=station_name,
            code=code,
            country='AU',
            state=None,
            elevation=None,
            location=point,
            is_active=True,
            data_source='user'
        )
        db.add(station)
        db.commit()
        db.refresh(station)

    # 3) Fetch current weather from configured provider
    weather_payload = None
    provider_used = None

    # Prefer OpenWeatherMap if configured
    owm_key = os.getenv('OWM_API_KEY')
    if owm_key and (payload.provider in ('auto', 'openweathermap')):
        try:
            params = {'lat': lat, 'lon': lon, 'units': 'metric', 'appid': owm_key}
            resp = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params, timeout=10)
            resp.raise_for_status()
            weather_payload = resp.json()
            provider_used = 'openweathermap'
        except requests.RequestException:
            weather_payload = None

    # Fallback to Open-Meteo (free) if needed
    if not weather_payload and (payload.provider in ('auto', 'open-meteo') or True):
        try:
            url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true'
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            weather_payload = resp.json()
            provider_used = 'open-meteo'
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f'Error fetching weather from providers: {e}')

    # 4) Map provider payload to WeatherData fields
    wd = WeatherData()
    wd.station_id = station.id
    wd.timestamp = datetime.utcnow()
    wd.data_source = provider_used
    wd.quality_score = 1.0

    try:
        if provider_used == 'openweathermap' and isinstance(weather_payload, dict):
            main = weather_payload.get('main', {})
            wind = weather_payload.get('wind', {})
            weather = (weather_payload.get('weather') or [{}])[0]
            wd.temperature = main.get('temp')
            wd.humidity = main.get('humidity')
            wd.pressure = main.get('pressure')
            # wind.speed is m/s; convert to km/h
            if wind.get('speed') is not None:
                wd.wind_speed = float(wind.get('speed')) * 3.6
            wd.wind_direction = wind.get('deg')
            # precipitation
            wd.precipitation = None
            if 'rain' in weather_payload:
                # try 1h rain
                wd.precipitation = weather_payload['rain'].get('1h') or weather_payload['rain'].get('3h')
            wd.weather_description = weather.get('description')

        elif provider_used == 'open-meteo' and isinstance(weather_payload, dict):
            current = weather_payload.get('current_weather') or {}
            wd.temperature = current.get('temperature')
            # Open-Meteo gives windspeed in km/h
            wd.wind_speed = current.get('windspeed')
            wd.wind_direction = current.get('winddirection')
            wd.humidity = None
            wd.pressure = None
            wd.precipitation = None
            wd.weather_description = None

    except Exception:
        # Non-fatal; continue with whatever fields were parsed
        pass

    # 5) Persist WeatherData
    db.add(wd)
    db.commit()
    db.refresh(wd)

    return {
        'station': {
            'id': station.id,
            'code': station.code,
            'name': station.name,
            'latitude': lat,
            'longitude': lon
        },
        'weather_record': {
            'id': wd.id,
            'timestamp': wd.timestamp.isoformat(),
            'data_source': wd.data_source,
            'temperature': wd.temperature,
            'humidity': wd.humidity,
            'pressure': wd.pressure,
            'wind_speed': wd.wind_speed,
            'precipitation': wd.precipitation,
            'weather_description': wd.weather_description
        }
    }

# Pydantic models for API responses
class WeatherStationResponse(BaseModel):
    id: int
    code: str
    name: str
    state: str
    elevation: float
    latitude: float
    longitude: float
    is_active: bool
    data_source: str
    
    class Config:
        from_attributes = True

class WeatherDataResponse(BaseModel):
    id: int
    station_code: str
    station_name: str
    timestamp: datetime
    temperature: Optional[float]
    humidity: Optional[float]
    pressure: Optional[float]
    wind_speed: Optional[float]
    precipitation: Optional[float]
    weather_description: Optional[str]
    
    class Config:
        from_attributes = True

@router.get("/stations", response_model=List[WeatherStationResponse])
async def get_weather_stations(db: Session = Depends(get_db)):
    """Get all weather stations with their coordinates"""
    
    # Query stations with coordinates
    result = db.execute(text("""
        SELECT s.id, s.code, s.name, s.state, s.elevation, s.is_active, s.data_source,
               ST_Y(s.location) as latitude, ST_X(s.location) as longitude
        FROM weather_stations s
        ORDER BY s.name
    """))
    
    stations = []
    for row in result:
        stations.append(WeatherStationResponse(
            id=row.id,
            code=row.code,
            name=row.name,
            state=row.state,
            elevation=row.elevation,
            latitude=row.latitude,
            longitude=row.longitude,
            is_active=row.is_active,
            data_source=row.data_source
        ))
    
    return stations

@router.get("/stations/{station_code}", response_model=WeatherStationResponse)
async def get_station_by_code(station_code: str, db: Session = Depends(get_db)):
    """Get a specific weather station by code"""
    
    result = db.execute(text("""
        SELECT s.id, s.code, s.name, s.state, s.elevation, s.is_active, s.data_source,
               ST_Y(s.location) as latitude, ST_X(s.location) as longitude
        FROM weather_stations s
        WHERE s.code = :code
    """), {"code": station_code})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Weather station not found")
    
    return WeatherStationResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        state=row.state,
        elevation=row.elevation,
        latitude=row.latitude,
        longitude=row.longitude,
        is_active=row.is_active,
        data_source=row.data_source
    )

@router.get("/weather/recent", response_model=List[WeatherDataResponse])
async def get_recent_weather(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent weather data across all stations"""
    
    recent_data = (db.query(WeatherData, WeatherStation)
                   .join(WeatherStation)
                   .order_by(WeatherData.timestamp.desc())
                   .limit(limit)
                   .all())
    
    weather_list = []
    for data, station in recent_data:
        weather_list.append(WeatherDataResponse(
            id=data.id,
            station_code=station.code,
            station_name=station.name,
            timestamp=data.timestamp,
            temperature=data.temperature,
            humidity=data.humidity,
            pressure=data.pressure,
            wind_speed=data.wind_speed,
            precipitation=data.precipitation,
            weather_description=data.weather_description
        ))
    
    return weather_list

@router.get("/weather/station/{station_code}", response_model=List[WeatherDataResponse])
async def get_weather_by_station(station_code: str, limit: int = 50, db: Session = Depends(get_db)):
    """Get weather data for a specific station"""
    
    # Check if station exists
    station = db.query(WeatherStation).filter(WeatherStation.code == station_code).first()
    if not station:
        raise HTTPException(status_code=404, detail="Weather station not found")
    
    # Get weather data
    weather_data = (db.query(WeatherData)
                    .filter(WeatherData.station_id == station.id)
                    .order_by(WeatherData.timestamp.desc())
                    .limit(limit)
                    .all())
    
    weather_list = []
    for data in weather_data:
        weather_list.append(WeatherDataResponse(
            id=data.id,
            station_code=station.code,
            station_name=station.name,
            timestamp=data.timestamp,
            temperature=data.temperature,
            humidity=data.humidity,
            pressure=data.pressure,
            wind_speed=data.wind_speed,
            precipitation=data.precipitation,
            weather_description=data.weather_description
        ))
    
    return weather_list

@router.get("/weather/nearby")
async def get_nearby_stations(lat: float, lng: float, radius_km: float = 100, db: Session = Depends(get_db)):
    """Find weather stations within a specified radius of a location"""
    
    result = db.execute(text("""
        SELECT s.code, s.name, s.state,
               ST_Y(s.location) as latitude, ST_X(s.location) as longitude,
               ST_Distance(
                   ST_Transform(s.location, 3857),
                   ST_Transform(ST_GeomFromText('POINT(' || :lng || ' ' || :lat || ')', 4326), 3857)
               ) / 1000 as distance_km
        FROM weather_stations s
        WHERE ST_Distance(
            ST_Transform(s.location, 3857),
            ST_Transform(ST_GeomFromText('POINT(' || :lng || ' ' || :lat || ')', 4326), 3857)
        ) <= :radius_m
        ORDER BY distance_km
    """), {"lat": lat, "lng": lng, "radius_m": radius_km * 1000})
    
    stations = []
    for row in result:
        stations.append({
            "code": row.code,
            "name": row.name,
            "state": row.state,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "distance_km": round(row.distance_km, 2)
        })
    
    return {
        "search_location": {"latitude": lat, "longitude": lng},
        "radius_km": radius_km,
        "stations_found": len(stations),
        "stations": stations
    }

@router.get("/statistics")
async def get_weather_statistics(db: Session = Depends(get_db)):
    """Get overall weather statistics"""
    
    # Basic counts
    station_count = db.query(WeatherStation).count()
    data_count = db.query(WeatherData).count()
    
    # Temperature statistics
    temp_stats = db.query(
        func.min(WeatherData.temperature).label('min_temp'),
        func.max(WeatherData.temperature).label('max_temp'),
        func.avg(WeatherData.temperature).label('avg_temp')
    ).first()
    
    # Date range
    date_range = db.query(
        func.min(WeatherData.timestamp).label('min_date'),
        func.max(WeatherData.timestamp).label('max_date')
    ).first()
    
    return {
        "stations": station_count,
        "total_records": data_count,
        "temperature": {
            "min": temp_stats.min_temp,
            "max": temp_stats.max_temp,
            "average": round(temp_stats.avg_temp, 1) if temp_stats.avg_temp else None
        },
        "date_range": {
            "from": date_range.min_date,
            "to": date_range.max_date
        }
    }

# =============================================================================
# BOM Weather Data API Routes
# =============================================================================

class BOMStationResponse(BaseModel):
    station_name: str
    station_code: Optional[str]
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    record_count: int
    date_range_start: str
    date_range_end: str
    avg_evapotranspiration: Optional[float]
    avg_rainfall: Optional[float]
    avg_max_temp: Optional[float]
    avg_min_temp: Optional[float]

class BOMTimeSeriesResponse(BaseModel):
    station_name: str
    metric: str
    start_date: Optional[str]
    end_date: Optional[str]
    data: List[dict]

@router.get("/bom/stations", response_model=List[BOMStationResponse])
async def get_bom_stations(db: Session = Depends(get_db)):
    """Get all BOM weather stations with summary statistics and coordinates"""
    try:
        result = db.execute(text("""
            SELECT 
                s.station_name,
                s.station_code,
                s.state,
                s.latitude,
                s.longitude,
                COUNT(d.id) as record_count,
                MIN(d.date) as date_range_start,
                MAX(d.date) as date_range_end,
                AVG(CASE 
                    WHEN d.evapotranspiration_mm >= 0 AND d.evapotranspiration_mm <= 50 
                    THEN d.evapotranspiration_mm 
                END) as avg_evapotranspiration,
                AVG(CASE 
                    WHEN d.rain_mm >= 0 AND d.rain_mm <= 500 
                    THEN d.rain_mm 
                END) as avg_rainfall,
                AVG(CASE 
                    WHEN d.max_temperature_c >= -30 AND d.max_temperature_c <= 60 
                    THEN d.max_temperature_c 
                END) as avg_max_temp,
                AVG(CASE 
                    WHEN d.min_temperature_c >= -30 AND d.min_temperature_c <= 50 
                    THEN d.min_temperature_c 
                END) as avg_min_temp
            FROM bom_weather_stations s
            LEFT JOIN bom_weather_data d ON s.station_name = d.station_name
            GROUP BY s.station_name, s.station_code, s.state, s.latitude, s.longitude
            ORDER BY s.station_name
        """))
        
        stations = []
        def safe_float(value):
            """Safely convert to float, handling NaN and None values"""
            if value is None:
                return None
            try:
                result = float(value)
                # Check for NaN or infinite values
                if not (result == result and abs(result) != float('inf')):  # NaN check: NaN != NaN
                    return None
                return round(result, 3)
            except (ValueError, TypeError):
                return None
        
        for row in result:
            stations.append(BOMStationResponse(
                station_name=row.station_name,
                station_code=row.station_code,
                state=row.state,
                latitude=safe_float(row.latitude),
                longitude=safe_float(row.longitude),
                record_count=row.record_count or 0,
                date_range_start=row.date_range_start.isoformat() if row.date_range_start else "",
                date_range_end=row.date_range_end.isoformat() if row.date_range_end else "",
                avg_evapotranspiration=safe_float(row.avg_evapotranspiration),
                avg_rainfall=safe_float(row.avg_rainfall),
                avg_max_temp=safe_float(row.avg_max_temp),
                avg_min_temp=safe_float(row.avg_min_temp)
            ))
        
        return stations
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BOM stations: {str(e)}")

@router.get("/bom/timeseries", response_model=BOMTimeSeriesResponse)
async def get_bom_timeseries(
    station_name: str,
    metric: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get time series data for a specific BOM station and metric"""
    try:
        # Validate metric
        valid_metrics = [
            'evapotranspiration_mm', 'rain_mm', 'pan_evaporation_mm',
            'max_temperature_c', 'min_temperature_c', 'max_relative_humidity_pct',
            'min_relative_humidity_pct', 'wind_speed_m_per_sec', 'solar_radiation_mj_per_sq_m'
        ]
        
        if metric not in valid_metrics:
            raise HTTPException(status_code=400, detail=f"Invalid metric. Valid options: {valid_metrics}")
        
        # Build query
        where_conditions = ["station_name = :station_name"]
        params = {"station_name": station_name}
        
        if start_date:
            where_conditions.append("date >= :start_date")
            params["start_date"] = start_date
            
        if end_date:
            where_conditions.append("date <= :end_date")
            params["end_date"] = end_date
        
        where_clause = " AND ".join(where_conditions)
        
        # Define reasonable ranges for each metric
        metric_ranges = {
            'evapotranspiration_mm': (0, 50),
            'rain_mm': (0, 500),
            'pan_evaporation_mm': (0, 50),
            'max_temperature_c': (-30, 60),
            'min_temperature_c': (-30, 50),
            'max_relative_humidity_pct': (0, 100),
            'min_relative_humidity_pct': (0, 100),
            'wind_speed_m_per_sec': (0, 100),
            'solar_radiation_mj_per_sq_m': (0, 50)
        }
        
        min_val, max_val = metric_ranges.get(metric, (None, None))
        range_condition = ""
        if min_val is not None and max_val is not None:
            range_condition = f"AND {metric} BETWEEN {min_val} AND {max_val}"
        
        query = text(f"""
            SELECT date, {metric} as value, station_name
            FROM bom_weather_data 
            WHERE {where_clause}
              AND {metric} IS NOT NULL
              {range_condition}
            ORDER BY date
        """)
        
        result = db.execute(query, params)
        
        def safe_float(value):
            """Safely convert to float, handling NaN and None values"""
            if value is None:
                return None
            try:
                result = float(value)
                # Check for NaN or infinite values
                if not (result == result and abs(result) != float('inf')):  # NaN check: NaN != NaN
                    return None
                return round(result, 3)
            except (ValueError, TypeError):
                return None
        
        data = []
        for row in result:
            data.append({
                "date": row.date.isoformat(),
                "value": safe_float(row.value),
                "station_name": row.station_name
            })
        
        return BOMTimeSeriesResponse(
            station_name=station_name,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            data=data
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching time series: {str(e)}")

@router.get("/bom/statistics")
async def get_bom_statistics(db: Session = Depends(get_db)):
    """Get overall statistics for the BOM weather dataset"""
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT station_name) as total_stations,
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                AVG(CASE 
                    WHEN evapotranspiration_mm >= 0 AND evapotranspiration_mm <= 50 
                    THEN evapotranspiration_mm 
                END) as avg_et,
                MIN(CASE 
                    WHEN evapotranspiration_mm >= 0 AND evapotranspiration_mm <= 50 
                    THEN evapotranspiration_mm 
                END) as min_et,
                MAX(CASE 
                    WHEN evapotranspiration_mm >= 0 AND evapotranspiration_mm <= 50 
                    THEN evapotranspiration_mm 
                END) as max_et,
                AVG(CASE 
                    WHEN rain_mm >= 0 AND rain_mm <= 500 
                    THEN rain_mm 
                END) as avg_rain,
                MIN(CASE 
                    WHEN rain_mm >= 0 AND rain_mm <= 500 
                    THEN rain_mm 
                END) as min_rain,
                MAX(CASE 
                    WHEN rain_mm >= 0 AND rain_mm <= 500 
                    THEN rain_mm 
                END) as max_rain,
                AVG(CASE 
                    WHEN max_temperature_c >= -30 AND max_temperature_c <= 60 
                    THEN max_temperature_c 
                END) as avg_max_temp,
                MIN(CASE 
                    WHEN max_temperature_c >= -30 AND max_temperature_c <= 60 
                    THEN max_temperature_c 
                END) as min_max_temp,
                MAX(CASE 
                    WHEN max_temperature_c >= -30 AND max_temperature_c <= 60 
                    THEN max_temperature_c 
                END) as max_max_temp,
                AVG(CASE 
                    WHEN min_temperature_c >= -30 AND min_temperature_c <= 50 
                    THEN min_temperature_c 
                END) as avg_min_temp,
                MIN(CASE 
                    WHEN min_temperature_c >= -30 AND min_temperature_c <= 50 
                    THEN min_temperature_c 
                END) as min_min_temp,
                MAX(CASE 
                    WHEN min_temperature_c >= -30 AND min_temperature_c <= 50 
                    THEN min_temperature_c 
                END) as max_min_temp
            FROM bom_weather_data
        """))
        
        def safe_float(value):
            """Safely convert to float, handling NaN and None values"""
            if value is None:
                return None
            try:
                result = float(value)
                # Check for NaN or infinite values
                if not (result == result and abs(result) != float('inf')):  # NaN check: NaN != NaN
                    return None
                return round(result, 3)
            except (ValueError, TypeError):
                return None
        
        row = result.fetchone()
        
        return {
            "dataset_overview": {
                "total_records": row.total_records,
                "total_stations": row.total_stations,
                "earliest_date": row.earliest_date.isoformat() if row.earliest_date else None,
                "latest_date": row.latest_date.isoformat() if row.latest_date else None
            },
            "evapotranspiration": {
                "average": safe_float(row.avg_et),
                "minimum": safe_float(row.min_et),
                "maximum": safe_float(row.max_et)
            },
            "rainfall": {
                "average": safe_float(row.avg_rain),
                "minimum": safe_float(row.min_rain),
                "maximum": safe_float(row.max_rain)
            },
            "temperature": {
                "max_average": safe_float(row.avg_max_temp),
                "max_minimum": safe_float(row.min_max_temp),
                "max_maximum": safe_float(row.max_max_temp),
                "min_average": safe_float(row.avg_min_temp),
                "min_minimum": safe_float(row.min_min_temp),
                "min_maximum": safe_float(row.max_min_temp)
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching statistics: {str(e)}")

@router.get("/bom/compare")
async def compare_bom_stations(
    stations: str,  # Comma-separated station names
    metric: str,
    aggregation: str = "monthly",
    db: Session = Depends(get_db)
):
    """Compare multiple BOM stations for a specific metric"""
    try:
        # Parse station names
        station_list = [s.strip() for s in stations.split(',')]
        
        # Validate inputs
        valid_metrics = [
            'evapotranspiration_mm', 'rain_mm', 'pan_evaporation_mm',
            'max_temperature_c', 'min_temperature_c', 'max_relative_humidity_pct',
            'min_relative_humidity_pct', 'wind_speed_m_per_sec', 'solar_radiation_mj_per_sq_m'
        ]
        
        if metric not in valid_metrics:
            raise HTTPException(status_code=400, detail=f"Invalid metric. Valid options: {valid_metrics}")
        
        # Determine aggregation function
        if aggregation == "daily":
            date_group = "date"
            date_format = "date"
        elif aggregation == "weekly":
            date_group = "DATE_TRUNC('week', date)"
            date_format = "DATE_TRUNC('week', date)"
        elif aggregation == "monthly":
            date_group = "DATE_TRUNC('month', date)"
            date_format = "DATE_TRUNC('month', date)"
        else:
            raise HTTPException(status_code=400, detail="Invalid aggregation. Valid options: daily, weekly, monthly")
        
        # Build query for multiple stations
        station_placeholders = ', '.join([f"'{station}'" for station in station_list])
        
        query = text(f"""
            SELECT 
                {date_format} as period,
                station_name,
                AVG({metric}) as avg_value
            FROM bom_weather_data 
            WHERE station_name IN ({station_placeholders})
              AND {metric} IS NOT NULL
            GROUP BY {date_group}, station_name
            ORDER BY period, station_name
        """)
        
        result = db.execute(query)
        
        def safe_float(value):
            """Safely convert to float, handling NaN and None values"""
            if value is None:
                return None
            try:
                result = float(value)
                # Check for NaN or infinite values
                if not (result == result and abs(result) != float('inf')):  # NaN check: NaN != NaN
                    return None
                return round(result, 3)
            except (ValueError, TypeError):
                return None
        
        data = {}
        for row in result:
            period = row.period.isoformat() if hasattr(row.period, 'isoformat') else str(row.period)
            if period not in data:
                data[period] = {}
            data[period][row.station_name] = safe_float(row.avg_value)
        
        return {
            "stations": station_list,
            "metric": metric,
            "aggregation": aggregation,
            "data": data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing stations: {str(e)}")
    

class FeedbackCreate(BaseModel):
    user_name: str
    user_email: str
    subject: str 
    message: str
    feedback_type: str

class FeedbackResponse(BaseModel):
    id: int
    user_name: str
    user_email: str
    subject: str 
    message: str
    feedback_type: str
    created_at: datetime
    updated_at: datetime

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackCreate):
    """Submit user feedback"""
    with SessionLocal() as session:
        db_feedback = Feedback(
            user_name=feedback.user_name,
            user_email=feedback.user_email,
            subject=feedback.subject,
            message=feedback.message,
            feedback_type=feedback.feedback_type
        )
        session.add(db_feedback)
        session.commit()
        session.refresh(db_feedback)
        return db_feedback

@router.get("/feedback", response_model=List[FeedbackResponse])
async def get_feedback(resolved: Optional[bool] = None):
    """Get all feedback (admin use)"""
    with SessionLocal() as session:
        query = session.query(Feedback)
        if resolved is not None:
            query = query.filter(Feedback.is_resolved == resolved)
        feedback_list = query.order_by(Feedback.created_at.desc()).all()
        return feedback_list

@router.put("/feedback/{feedback_id}")
async def update_feedback_status(feedback_id: int, is_resolved: bool):
    """Update feedback resolution status (admin use)"""
    with SessionLocal() as session:
        feedback = session.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        feedback.is_resolved = is_resolved
        feedback.updated_at = datetime.utcnow()
        session.commit()
        return {"message": "Feedback status updated"}


# ============================================================================
# Gemini AI Analysis Endpoints
# ============================================================================

from app.services.gemini_analysis_service import gemini_service

class WeatherAnalysisRequest(BaseModel):
    """Request model for weather analysis"""
    metric: str  # 'temperature', 'wind', 'humidity'
    data: dict  # Chart data
    station_name: str
    date_range: Optional[str] = None


@router.post("/analysis/generate")
async def generate_weather_analysis(request: WeatherAnalysisRequest, db: Session = Depends(get_db)):
    """
    Generate AI-powered weather analysis using Gemini API with database caching
    
    Args:
        request: Analysis request with metric type and data
        db: Database session for caching
        
    Returns:
        Generated analysis text
    """
    try:
        metric = request.metric.lower()
        
        if metric == 'temperature':
            analysis = await gemini_service.generate_temperature_analysis(
                data=request.data,
                station_name=request.station_name,
                date_range=request.date_range,
                db=db
            )
        elif metric == 'wind':
            analysis = await gemini_service.generate_wind_analysis(
                data=request.data,
                station_name=request.station_name,
                date_range=request.date_range,
                db=db
            )
        elif metric == 'humidity':
            analysis = await gemini_service.generate_humidity_analysis(
                data=request.data,
                station_name=request.station_name,
                date_range=request.date_range,
                db=db
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")
        
        return {
            "success": True,
            "metric": metric,
            "analysis": analysis,
            "gemini_configured": gemini_service.is_configured()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating analysis: {str(e)}")


@router.get("/analysis/status")
async def get_analysis_status():
    """Check if Gemini API is configured and available"""
    return {
        "gemini_configured": gemini_service.is_configured(),
        "api_available": gemini_service.is_configured()
    }
