"""
Database connection and session management
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv
from typing import Generator, Optional

# Load environment variables
# Try different encoding methods to handle various .env file formats
try:
    # First try with explicit UTF-8 encoding
    load_dotenv(encoding='utf-8')
except (UnicodeDecodeError, Exception) as e:
    try:
        # If UTF-8 fails, try without encoding parameter (let dotenv handle it)
        load_dotenv()
    except Exception:
        # If that also fails, try reading file manually and setting env vars
        import sys
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            except Exception:
                pass  # If all fails, continue with default values

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://sigorta_user:sigorta_pass@localhost:3306/sigorta_db"
)

# Check if we should use SQLite fallback
USE_SQLITE_FALLBACK = os.getenv("USE_SQLITE_FALLBACK", "false").lower() == "true"

# Engine configuration with error handling
engine = None
SessionLocal = None

try:
    if USE_SQLITE_FALLBACK:
        # Use SQLite for development/testing
        DATABASE_URL = "sqlite:///./sigorta.db"
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False
        )
    else:
        # Try MySQL connection
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Connection health check
            echo=False,  # SQL query logging (production'da False)
            connect_args={
                "charset": "utf8mb4",
                "connect_timeout": 10,
            }
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    
    # Session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("[OK] Database connection successful")
except Exception as e:
    print(f"[WARNING] Database connection failed: {e}")
    print("[WARNING] Application will continue without database. Some features may not work.")
    # Create a dummy session factory that raises an error when used
    class DummySession:
        def __enter__(self):
            raise Exception("Database not available. Please start MySQL or set USE_SQLITE_FALLBACK=true")
        def __exit__(self, *args):
            pass
    SessionLocal = None


def get_db() -> Generator[Optional[Session], None, None]:
    """
    Database session dependency for FastAPI
    Returns None if database is not available
    Usage:
        @app.get("/items")
        def get_items(db: Optional[Session] = Depends(get_db)):
            if db is None:
                # Handle no database case
                ...
    """
    if SessionLocal is None:
        yield None
        return
    
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # If connection fails, yield None instead of raising
        print(f"[WARNING] Database session error: {e}")
        yield None
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def init_db():
    """
    Create all tables
    Call this once at application startup
    """
    if engine is None:
        print("[WARNING] Database not available, skipping table creation")
        return
    
    try:
        from backend.models import Base
        Base.metadata.create_all(bind=engine)
        print("[OK] Database tables created successfully")
    except Exception as e:
        print(f"[WARNING] Failed to create database tables: {e}")


def drop_db():
    """
    Drop all tables (DANGER: Use only in development!)
    """
    if engine is None:
        print("[WARNING] Database not available, cannot drop tables")
        return
    
    try:
        from backend.models import Base
        Base.metadata.drop_all(bind=engine)
        print("[WARNING] All database tables dropped")
    except Exception as e:
        print(f"[WARNING] Failed to drop database tables: {e}")

