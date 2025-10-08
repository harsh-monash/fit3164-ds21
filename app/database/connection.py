from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+pg8000://postgres:password@localhost:5433/weatherdb"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=True if os.getenv("DEBUG", "False").lower() == "true" else False
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
async def init_db():
    """Initialize database and create tables"""
    try:

        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully")

        # Test PostGIS extension
        with engine.connect() as connection:
            result = connection.execute(text("SELECT PostGIS_Version();"))
            version = result.fetchone()
            print(f"✅ PostGIS version: {version[0] if version else 'Not available'}")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise
