#!/usr/bin/env python3
"""
NSW Weather Dashboard - FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path
from fastapi import FastAPI
from app.auth import auth_routes 
from app.routes import stations

def root():
    return {"message": "Weather Visualization + 2FA API Running"}


# Import API routes
try:
    from app.api.api_routes import router as api_router
except ImportError:
    print("Warning: Could not import API routes")
    api_router = None

# Create FastAPI app
app = FastAPI(
    title="NSW Weather Dashboard",
    description="Weather monitoring and analysis dashboard for NSW, Australia",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


app.include_router(auth_routes.router)
app.include_router(stations.router)

# Include API routes if available
if api_router:
    # Include API routes
    app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    """Root endpoint - serve dashboard"""
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(str(dashboard_path))
    return {"message": "NSW Weather Dashboard API", "status": "running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "nsw-weather-dashboard"}

@app.get("/dashboard")
async def dashboard():
    """Dashboard endpoint"""
    dashboard_path = Path(__file__).parent / "static" / "dashboard.html" 
    if dashboard_path.exists():
        return FileResponse(str(dashboard_path))
    return {"message": "Dashboard not found", "status": "error"}

@app.get("/visualisation")
async def weather_visualization():
    """Weather data visualization page with advanced analytics"""
    viz_path = Path(__file__).parent / "static" / "weather_dashboard.html"
    if viz_path.exists():
        return FileResponse(str(viz_path))
    return {"message": "Weather visualization not found", "status": "error"}

@app.get("/index")
async def test_index():
    """Test index endpoint"""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Index page not found", "status": "error"}

@app.get("/analysis")
async def weather_analysis():
    """Alias for weather visualization page"""
    viz_path = Path(__file__).parent / "static" / "weather_visualization.html"
    if viz_path.exists():
        return FileResponse(str(viz_path))
    return {"message": "Weather analysis not found", "status": "error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
