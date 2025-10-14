#!/usr/bin/env python3
"""
Initialize the PostGIS database for the weather project.
"""

import os
import pg8000
from dotenv import load_dotenv

def main():
    # 1️⃣ Load .env from project root
    load_dotenv(dotenv_path="config/.env")

    # 2️⃣ Gather connection parameters
    db_url = os.getenv("DATABASE_URL")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", 5432))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    database = os.getenv("POSTGRES_DB", "weatherdb")

    print("🚀 Initializing Weather Database with PostGIS...")
    print(f"Connecting to {host}:{port} as {user} -> {database}")

    try:
        # 3️⃣ Connect to Postgres
        conn = pg8000.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database
        )
        cur = conn.cursor()

        # 4️⃣ Create PostGIS extensions if not present
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")
        conn.commit()

        print("✅ PostGIS setup successful.")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ PostGIS setup failed: {e}")
        raise

if __name__ == "__main__":
    main()
