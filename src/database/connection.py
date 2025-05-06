"""Database connection management for SQL Server."""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- New SQLite support ---
def get_sqlite_connection_string() -> str:
    """Get SQLite connection string from environment variable or default."""
    sqlite_path = os.getenv("DB_SQLITE_PATH", "indeed_jobs_local.sqlite3")
    return f"sqlite:///{sqlite_path}"

# --- Existing SQL Server support ---
def get_connection_string() -> str:
    """Generate Windows authentication database connection string."""
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME", "IndeedJobs")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    driver_formatted = driver.replace(" ", "+")
    # Escape server name if it contains a single backslash but not a double backslash
    if server and ('\\' not in server and '\\' in server):
        server = server.replace('\\', '\\\\')
    return f"mssql+pyodbc://{server}/{database}?driver={driver_formatted}&trusted_connection=yes"

# --- Engine selection logic ---
if os.getenv("DB_SQLITE_PATH"):
    CONNECTION_STRING = get_sqlite_connection_string()
    logger.info(f"Using SQLite connection: {CONNECTION_STRING}")
else:
    CONNECTION_STRING = get_connection_string()
    logger.info(f"Using SQL Server connection: {CONNECTION_STRING}")

try:
    # Enable SQL debug logging if specified
    echo = os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true"
    
    # Create engine and session factory
    engine = create_engine(CONNECTION_STRING, echo=echo)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create base class for declarative models
    Base = declarative_base()
    
    logger.info("Database connection established")
except Exception as e:
    logger.error(f"Error connecting to database: {e}")
    raise

def get_db_session() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        logger.error(f"Error creating database session: {e}")
        raise

def init_db() -> None:
    """Initialize the database with required tables."""
    from .job_schema import Base
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def init_sqlite_db() -> None:
    """Initialize a local SQLite database with the same schema."""
    from .job_schema import Base
    try:
        sqlite_engine = create_engine(get_sqlite_connection_string())
        Base.metadata.create_all(bind=sqlite_engine)
        logger.info("SQLite database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating SQLite database tables: {e}")
        raise 