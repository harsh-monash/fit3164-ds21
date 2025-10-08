# NSW Weather Dashboard - Project Structure

## Directory Overview

```
d:\FIT3164\
├── app/                           # Main application code
│   ├── main.py                   # FastAPI entry point
│   ├── core/                     # Core infrastructure
│   ├── api/                      # API routes and endpoints
│   ├── database/                 # Database models and connections
│   ├── models/                   # Pydantic models
│   ├── services/                 # Business logic services
│   ├── static/                   # Frontend assets (CSS, JS, images)
│   └── templates/                # HTML templates
│
├── data/                          # Data storage and processing
│   ├── raw/                      # Original data files (BOM stations, etc.)
│   └── processed/                # Processed data outputs
│
├── scripts/                       # Organized utility scripts
│   ├── geocoding/                # Location and coordinate processing
│   │   ├── add_station_coordinates.py
│   │   ├── batch_geocode_bom_stations.py
│   │   └── geocode_missing_stations.py
│   │
│   ├── ingestion/                # Database ingestion and sync
│   │   ├── cleanup_stations.py
│   │   ├── sync_all_stations.py
│   │   └── update_station_data.py
│   │
│   ├── utilities/                # General purpose tools
│   │   ├── bom_data_filter.py
│   │   ├── bom_models.py
│   │   ├── check_bom_*.py (multiple check scripts)
│   │   ├── extract_*.py (multiple extraction scripts)
│   │   ├── list_missing_station_coords.py
│   │   ├── match_unmatched_from_txt.py
│   │   └── prepare_exact_matches.py
│   │
│   ├── validation/               # Testing and validation
│   │   ├── check_data_structure.py
│   │   ├── test_bom_download.py
│   │   └── validate_bom_data.py
│   │
│   └── cleanup/                  # Legacy cleanup scripts
│
├── logs/                          # Application and process logs
│   ├── batch_geocoding.log
│   ├── bom_geocoding.log
│   └── station_update.log
│
├── temp/                          # Temporary files and testing
│   ├── test_button.html
│   └── test_server.py
│
├── tests/                         # Test suite
├── dummy/                         # Test data generation
├── .github/                       # GitHub configurations
├── docs/                          # Documentation
└── [Root Config Files]            # Docker, requirements, etc.
```

## Script Categories

### Geocoding Scripts (`scripts/geocoding/`)
- **Purpose**: Handle location lookup and coordinate assignment
- **Key Files**:
  - `batch_geocode_bom_stations.py` - Bulk geocoding with rate limiting
  - `add_station_coordinates.py` - Individual coordinate updates
  - `geocode_missing_stations.py` - Fill missing location data

### Ingestion Scripts (`scripts/ingestion/`)
- **Purpose**: Database operations and data synchronization
- **Key Files**:
  - `sync_all_stations.py` - Synchronize station registry with weather data
  - `cleanup_stations.py` - Remove duplicates and inconsistencies
  - `update_station_data.py` - Refresh station information

### Utility Scripts (`scripts/utilities/`)
- **Purpose**: Data processing, extraction, and general tools
- **Key Files**:
  - `bom_models.py` - Data models for BOM integration
  - `extract_*.py` - Various data extraction tools
  - `check_*.py` - Data validation and status checks
  - `match_unmatched_from_txt.py` - Station matching algorithms

### Validation Scripts (`scripts/validation/`)
- **Purpose**: Testing, verification, and data quality checks
- **Key Files**:
  - `validate_bom_data.py` - Comprehensive data validation
  - `test_bom_download.py` - API connection testing
  - `check_data_structure.py` - Database structure verification

## Data Organization

### Raw Data (`data/raw/`)
- Original BOM station files
- Unprocessed CSV exports
- Reference datasets

### Processed Data (`data/processed/`)
- Matched station coordinates
- Geocoding results
- Analysis outputs

## Usage Guidelines

1. **Development**: Use scripts from appropriate categories
2. **Production**: Main application runs from `app/main.py` or `start_server.py`
3. **Maintenance**: Check logs in `logs/` directory
4. **Testing**: Use validation scripts and `temp/` for experiments

## Database Status
- **Stations**: 518 total (438 with coordinates, 80 without)
- **Weather Data**: Synchronized with station registry
- **Spatial Data**: PostGIS enabled for geographic queries

This structure provides clear separation of concerns and makes the codebase more maintainable.