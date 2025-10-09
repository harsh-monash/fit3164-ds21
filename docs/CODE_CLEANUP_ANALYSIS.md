# Code Cleanup Analysis

**Date:** 2025-01-25  
**Purpose:** Identify redundant code files outside the `app/` folder

---

## Summary

Your main application code is correctly stored in the `app/` folder. After analyzing all directories, I've identified several folders containing **redundant or outdated code** that can be safely removed or archived.

**Key Finding:** The `frontend/` folder appears to contain **old/duplicate frontend code** that has been superseded by `app/static/`.

---

## Directory Analysis

### ✅ KEEP - Essential Files

#### Root Directory Files
- ✅ `start_server.py` - **KEEP** - Server entry point
- ✅ `init_db.py` - **KEEP** - Database initialization
- ⚠️ `check.py` - Evaluate if still used
- ⚠️ `check_licenses.py` - Evaluate if still used

#### `app/` Folder
- ✅ **KEEP ENTIRE FOLDER** - This is your main application
  - `main.py` - FastAPI entry point
  - `api/` - API endpoints
  - `auth/` - Authentication
  - `core/` - Core configuration
  - `database/` - Database models and connections
  - `services/` - Business logic
  - `static/` - Frontend assets (HTML, CSS, JS)

---

### 🗄️ ARCHIVE - Keep for Reference (Optional)

#### `weather_data/` - Data Ingestion Scripts (8 files)
**Recommendation:** Archive or keep if you need to re-ingest BOM data

Files:
- `add_station_coordinates.py`
- `bom_ingest.py`
- `bom_models.py`
- `geocode_missing_stations.py`
- `ingest_bom_data.py`
- `list_missing_station_coords.py`
- `populate_bom_stations.py`
- `validate_bom_data.py`

**Reasoning:** These were likely used to initially populate your database with BOM weather stations. If you don't plan to re-ingest data, these can be archived. If you need to update station data periodically, keep them.

---

#### `scripts/` - Utility Scripts (Multiple subdirectories)
**Recommendation:** Review and archive most, keep only active scripts

**Subdirectories:**
1. `scripts/cleanup/` (2 files)
   - `find_empty_files.ps1`
   - `find_empty_files.py`
   - **Action:** Remove if not actively used

2. `scripts/ingestion/` (14 files) ⚠️ **High Redundancy**
   - `bom_data.py`
   - `bom_ingest.py` ← Duplicate of weather_data/bom_ingest.py
   - `cleanup_stations.py`
   - `geocode_and_ingest.py`
   - `improved_bom_ingestion.py`
   - `ingest_all_states.py`
   - `ingest_bom_data.py` ← Duplicate of weather_data/ingest_bom_data.py
   - `ingest_matches.py`
   - `populate_bom_stations.py` ← Duplicate of weather_data/populate_bom_stations.py
   - `sync_all_stations.py`
   - `update_station_data.py`
   - Plus log files: `*.log`
   - **Action:** This folder has MANY duplicates of weather_data/. Archive or delete.

3. `scripts/validation/` (3 files)
   - `check_data_structure.py`
   - `test_bom_download.py`
   - `validate_bom_data.py` ← Duplicate of weather_data/validate_bom_data.py
   - **Action:** Archive if not actively used

4. `scripts/geocoding/` - Not checked yet
5. `scripts/utilities/` - Not checked yet
6. `watch-empty-files.ps1` - Utility script

**Overall:** The `scripts/` folder appears to contain many duplicates and old versions of ingestion scripts. **High redundancy.**

---

### ❌ REMOVE - Redundant/Outdated Code

#### `frontend/` - **HIGHLY REDUNDANT** ⚠️
**Recommendation:** **REMOVE** - Old frontend code superseded by `app/static/`

Contents:
- `frontend/js/dashboard.js` - Old version
- `frontend/css/dashboard.css` - Old version
- `frontend/dashboard.html` - Old version
- `frontend/static/` - Unknown contents

**Comparison with app/static/:**
- `app/static/` contains:
  - `index.html` (main landing page - 933 lines, recently updated)
  - `dashboard.html` (active dashboard)
  - `weather_visualization.html` (active page)
  - `js/` folder with active JavaScript files
  - `css/` folder with active stylesheets

**Reasoning:** You have a complete frontend in `app/static/`. The `frontend/` folder appears to be an old/abandoned version. The fact that `app/static/dashboard.html` exists and is actively served by your FastAPI app confirms that `frontend/dashboard.html` is outdated.

**Action:** **DELETE ENTIRE `frontend/` FOLDER**

---

#### `temp/` - Temporary Files
**Recommendation:** **REMOVE**

Contents:
- `test_button.html` - Temporary test file
- `test_server.py` - Temporary test script

**Reasoning:** These are clearly temporary test files. Safe to delete.

**Action:** **DELETE ENTIRE `temp/` FOLDER**

---

#### `dummy/` - Dummy Data Scripts
**Recommendation:** **REMOVE** (unless actively used in testing)

Contents:
- `demo_database.py` - Generate demo data
- `generate_dummy_data.py` - Generate dummy data
- `verify_data.py` - Verify dummy data

**Reasoning:** These were likely used for initial testing/development. If you have real BOM data now (518 stations), you don't need dummy data generators.

**Action:** **DELETE ENTIRE `dummy/` FOLDER** (unless you use these for automated testing)

---

#### `tools/` - Empty Folder
**Recommendation:** **REMOVE**

**Action:** **DELETE `tools/` FOLDER**

---

### 🧪 TESTING - Evaluate

#### `testing/` - Test Files (8 files)
**Recommendation:** KEEP if tests are part of your CI/CD, otherwise REMOVE

Files:
- `test.py`
- `test_api.py` - Tests API endpoints
- `test_cleaning.py` - Tests data cleaning
- `test_database.py` - Tests database operations
- `test_db_connection.py` - Tests DB connection
- `test_ftp_connection.py` - Tests FTP connection
- `test_http_alternative.py` - Tests HTTP
- `test_spatial.py` - Tests spatial queries

**Questions to Consider:**
1. Do you run these tests regularly?
2. Are they part of your CI/CD pipeline?
3. Do they still work with your current codebase?

**If YES:** Keep them and consider moving to `app/tests/` for better organization  
**If NO:** Archive or delete

---

## Redundancy Summary

### 🔴 High Redundancy - Duplicates Found

1. **`frontend/` vs `app/static/`**
   - `frontend/js/dashboard.js` ← OLD
   - `app/static/js/dashboard.js` ← CURRENT (1353 lines, recently updated)
   - **Action:** Delete `frontend/`

2. **`scripts/ingestion/` vs `weather_data/`**
   - `scripts/ingestion/bom_ingest.py` ← Duplicate
   - `weather_data/bom_ingest.py` ← Likely the source
   - `scripts/ingestion/ingest_bom_data.py` ← Duplicate
   - `weather_data/ingest_bom_data.py` ← Likely the source
   - `scripts/ingestion/populate_bom_stations.py` ← Duplicate
   - `weather_data/populate_bom_stations.py` ← Likely the source
   - `scripts/ingestion/validate_bom_data.py` ← Duplicate
   - `weather_data/validate_bom_data.py` ← Likely the source
   - **Action:** Delete `scripts/ingestion/` or consolidate

3. **Multiple ingestion script versions:**
   - `scripts/ingestion/improved_bom_ingestion.py`
   - `scripts/ingestion/ingest_all_states.py`
   - `scripts/ingestion/geocode_and_ingest.py`
   - These appear to be iterations/experiments
   - **Action:** Keep only the final working version

---

## Recommended Actions

### Phase 1: Safe Deletions (No Risk)
```powershell
# Delete temporary files
Remove-Item -Recurse -Force "d:\FIT3164\temp"

# Delete empty tools folder
Remove-Item -Recurse -Force "d:\FIT3164\tools"

# Delete old frontend code (BACKUP FIRST if unsure)
Remove-Item -Recurse -Force "d:\FIT3164\frontend"
```

### Phase 2: Conditional Deletions (Low Risk)
```powershell
# Delete dummy data generators (unless used in tests)
Remove-Item -Recurse -Force "d:\FIT3164\dummy"

# Delete redundant scripts folder (after backing up any unique scripts)
Remove-Item -Recurse -Force "d:\FIT3164\scripts"
```

### Phase 3: Archive for Reference (Optional)
```powershell
# Create archive folder
New-Item -ItemType Directory -Path "d:\FIT3164\archive"

# Move data ingestion scripts to archive
Move-Item "d:\FIT3164\weather_data" "d:\FIT3164\archive\weather_data"

# Move testing files to archive (if not actively used)
Move-Item "d:\FIT3164\testing" "d:\FIT3164\archive\testing"
```

### Phase 4: Git Cleanup (Optional)
```powershell
# After deleting, commit changes
git add -A
git commit -m "chore: remove redundant code files and folders

- Deleted temp/ folder (temporary test files)
- Deleted tools/ folder (empty)
- Deleted frontend/ folder (old frontend, superseded by app/static/)
- Deleted dummy/ folder (dummy data generators no longer needed)
- Deleted scripts/ folder (redundant ingestion scripts)
- Archived weather_data/ and testing/ for reference"

# Push to remote
git push origin Sam_dev
```

---

## Folders to Keep

✅ **Essential folders:**
- `app/` - Main application code
- `.github/` - GitHub Actions workflows
- `.vscode/` - VS Code settings
- `data/` - Data files (if actively used)
- `logs/` - Application logs
- `config/` - Configuration files
- `docs/` - Documentation
- `node_modules/` - NPM dependencies (if using Node.js tools)

---

## Final Structure (After Cleanup)

```
d:\FIT3164\
├── .github/              ✅ Keep (workflows)
├── .vscode/              ✅ Keep (editor settings)
├── app/                  ✅ Keep (MAIN APPLICATION)
│   ├── api/
│   ├── auth/
│   ├── core/
│   ├── database/
│   ├── services/
│   ├── static/           ← Your frontend (HTML, CSS, JS)
│   └── main.py
├── config/               ✅ Keep (if has configs)
├── data/                 ✅ Keep (if actively used)
├── docs/                 ✅ Keep (documentation)
├── logs/                 ✅ Keep (application logs)
├── node_modules/         ✅ Keep (if using npm)
├── archive/              📦 NEW (archived code for reference)
│   ├── weather_data/     (data ingestion scripts)
│   └── testing/          (old test files)
├── start_server.py       ✅ Keep (entry point)
├── init_db.py            ✅ Keep (DB initialization)
├── requirements.txt      ✅ Keep (Python dependencies)
├── Dockerfile            ✅ Keep (Docker config)
├── docker-compose.yml    ✅ Keep (Docker compose)
└── README.md             ✅ Keep (documentation)
```

**Folders REMOVED:**
- ❌ `frontend/` - Old frontend code
- ❌ `temp/` - Temporary test files
- ❌ `dummy/` - Dummy data generators
- ❌ `tools/` - Empty folder
- ❌ `scripts/` - Redundant ingestion scripts
- ❌ `testing/` - Outdated test files (or moved to archive/)
- ❌ `weather_data/` - Data ingestion scripts (or moved to archive/)

---

## Questions Before Proceeding

1. **Do you still need to re-ingest BOM weather station data?**
   - If YES: Keep `weather_data/`
   - If NO: Archive or delete

2. **Are the test files in `testing/` part of your CI/CD?**
   - If YES: Move to `app/tests/` and keep
   - If NO: Archive or delete

3. **Do you use dummy data for automated testing?**
   - If YES: Keep `dummy/`
   - If NO: Delete

4. **Should I create a backup before deleting?**
   - Recommended: Yes, especially for `frontend/` and `scripts/`

---

## Next Steps

**Option 1: Conservative Approach (Recommended)**
1. Create `archive/` folder
2. Move questionable folders to archive
3. Test application thoroughly
4. Delete archive after confirming everything works

**Option 2: Aggressive Cleanup**
1. Delete all redundant folders immediately
2. Git can recover if needed (`git checkout -- <file>`)
3. Faster but higher risk

**Let me know which approach you prefer, and I'll execute the cleanup for you!**
