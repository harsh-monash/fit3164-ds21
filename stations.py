# app/routes/stations.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from app.database.connection import engine

router = APIRouter(prefix="/api/v1/stations", tags=["stations"])

@router.get("/latest-geojson")
def latest_geojson(
    hot_threshold: float = Query(30.0, description="Temp °C threshold for 'hot'"),
    wet_threshold: float = Query(70.0, description="RH % threshold for 'wet'")
):
    """
    Returns station points as a GeoJSON FeatureCollection with latest T/RH/Wind/Pressure.
    Assumes tables:
      stations(id, name, geom geometry(Point, 4326), ... )
      readings(id, station_id, observed_at timestamptz, temperature, humidity, wind_speed, pressure)
    Adjust table/column names to your schema if needed.
    """
    sql = text("""
    WITH latest AS (
      SELECT r.*
      FROM readings r
      JOIN (
        SELECT station_id, MAX(observed_at) AS latest_ts
        FROM readings
        GROUP BY station_id
      ) m ON m.station_id = r.station_id AND m.latest_ts = r.observed_at
    )
    SELECT
      s.id,
      s.name,
      ST_AsGeoJSON(s.geom)::json AS geometry,
      l.temperature,
      l.humidity,
      l.wind_speed,
      l.pressure,
      l.observed_at,
      (l.temperature >= :hot) AS is_hot,
      (l.humidity    >= :wet) AS is_wet
    FROM stations s
    LEFT JOIN latest l ON l.station_id = s.id
    WHERE s.geom IS NOT NULL;
    """)

    with engine.connect() as conn:
        rows = conn.execute(sql, {"hot": hot_threshold, "wet": wet_threshold}).mappings().all()

    features = []
    for r in rows:
        geom = r["geometry"]  # already JSON (dict)
        props = {
            "station_id": r["id"],
            "name": r["name"],
            "temperature": r["temperature"],
            "humidity": r["humidity"],
            "wind_speed": r["wind_speed"],
            "pressure": r["pressure"],
            "observed_at": r["observed_at"].isoformat() if r["observed_at"] else None,
            "is_hot": bool(r["is_hot"]) if r["is_hot"] is not None else None,
            "is_wet": bool(r["is_wet"]) if r["is_wet"] is not None else None,
        }
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}
