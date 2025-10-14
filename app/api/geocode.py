# app/api/geocode.py
from fastapi import APIRouter, Depends, Response
from app.deps.http import get_client
from app.utils.cache import get, set_

router = APIRouter()

@router.get("/search")
async def geocode(q: str, response: Response, client=Depends(get_client)):
    key = f"geo:{q.strip().lower()}"
    hit = get(key, ttl=3600)
    if hit:
        response.headers["X-Cache"] = "HIT"
        response.headers["Cache-Control"] = "public, max-age=300"
        return hit

    r = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "jsonv2", "limit": 5},
        headers={"Accept-Language": "en"}
    )
    r.raise_for_status()
    data = r.json()
    set_(key, data, ttl=3600)
    response.headers["X-Cache"] = "MISS"
    response.headers["Cache-Control"] = "public, max-age=300"
    return data
