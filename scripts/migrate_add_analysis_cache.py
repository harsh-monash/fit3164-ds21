"""
Database Migration: Add Weather Analysis Cache Table
Creates a new table to store AI-generated weather analyses for caching
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_file = Path(__file__).parent.parent / 'config' / '.env'
if env_file.exists():
    load_dotenv(env_file)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://weather_user:weather_pass@localhost:5432/weather_db')

def create_analysis_cache_table():
    """Create the weather_analysis_cache table"""
    
    engine = create_engine(DATABASE_URL)
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS weather_analysis_cache (
        id SERIAL PRIMARY KEY,
        station_name VARCHAR(255) NOT NULL,
        metric_type VARCHAR(50) NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        data_hash VARCHAR(64) NOT NULL,
        analysis_text TEXT NOT NULL,
        model_used VARCHAR(100) DEFAULT 'gemini-1.5-flash',
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        access_count INTEGER DEFAULT 0,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_valid BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for fast lookups
    CREATE INDEX IF NOT EXISTS idx_analysis_station_metric 
        ON weather_analysis_cache(station_name, metric_type);
    
    CREATE INDEX IF NOT EXISTS idx_analysis_dates 
        ON weather_analysis_cache(start_date, end_date);
    
    CREATE INDEX IF NOT EXISTS idx_analysis_hash 
        ON weather_analysis_cache(data_hash);
    
    -- Create composite index for unique constraint
    CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_unique 
        ON weather_analysis_cache(station_name, metric_type, data_hash);
    
    -- Create index for cleanup queries
    CREATE INDEX IF NOT EXISTS idx_analysis_generated_at 
        ON weather_analysis_cache(generated_at DESC);
    """
    
    try:
        with engine.connect() as conn:
            # Execute the SQL
            conn.execute(text(create_table_sql))
            conn.commit()
            print("✓ Successfully created weather_analysis_cache table and indexes")
            
            # Verify table was created
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_name = 'weather_analysis_cache'
            """))
            count = result.fetchone()[0]
            
            if count > 0:
                print("✓ Table verified in database")
                
                # Show table structure
                result = conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'weather_analysis_cache'
                    ORDER BY ordinal_position
                """))
                
                print("\nTable structure:")
                print("-" * 60)
                for row in result:
                    nullable = "NULL" if row[2] == "YES" else "NOT NULL"
                    print(f"  {row[0]:<25} {row[1]:<20} {nullable}")
                print("-" * 60)
                
                return True
            else:
                print("✗ Table creation verification failed")
                return False
                
    except Exception as e:
        print(f"✗ Error creating table: {str(e)}")
        return False
    finally:
        engine.dispose()


def drop_analysis_cache_table():
    """Drop the weather_analysis_cache table (for rollback)"""
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS weather_analysis_cache CASCADE"))
            conn.commit()
            print("✓ Successfully dropped weather_analysis_cache table")
            return True
    except Exception as e:
        print(f"✗ Error dropping table: {str(e)}")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Weather Analysis Cache - Database Migration")
    print("=" * 60)
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        print("Rolling back migration (dropping table)...")
        if drop_analysis_cache_table():
            print("\n✓ Rollback completed successfully")
        else:
            print("\n✗ Rollback failed")
            sys.exit(1)
    else:
        print("Creating weather_analysis_cache table...")
        if create_analysis_cache_table():
            print("\n✓ Migration completed successfully")
            print("\nNext steps:")
            print("1. Restart your application")
            print("2. AI analyses will now be cached automatically")
            print("3. Subsequent requests will be instant!")
        else:
            print("\n✗ Migration failed")
            sys.exit(1)
    
    print("\n" + "=" * 60)
