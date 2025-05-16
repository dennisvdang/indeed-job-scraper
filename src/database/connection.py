"""Database connection management module."""

import os
import logging
from typing import Optional, Callable, ContextManager, Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from contextlib import contextmanager
from dotenv import load_dotenv

# Configure logger
logger = logging.getLogger(__name__)

# Create base class for declarative models
Base = declarative_base()

class DatabaseManager:
    """Database connection manager with dependency injection support."""
    
    def __init__(
        self,
        connection_string: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_pre_ping: bool = True
    ) -> None:
        """
        Initialize database manager with connection parameters.
        
        Args:
            connection_string: SQLAlchemy connection string
            echo: Whether to echo SQL statements for debugging
            pool_size: Connection pool size
            max_overflow: Maximum number of connections to allow in the connection pool "overflow"
            pool_pre_ping: Ping connections before use to avoid stale connections
        """
        self.connection_string = connection_string
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[scoped_session] = None
        
        logger.info(f"Initializing database manager with connection: {self._mask_connection_string()}")
        self._create_engine()
    
    def _mask_connection_string(self) -> str:
        """Mask sensitive information in connection string for logging."""
        if 'sqlite' in self.connection_string:
            return self.connection_string
        
        # Mask passwords in connection string
        if 'password=' in self.connection_string.lower():
            return self.connection_string.replace(
                self.connection_string.split('password=')[1].split('&')[0], 
                '********'
            )
        return self.connection_string
    
    def _create_engine(self) -> None:
        """Create SQLAlchemy engine."""
        try:
            self._engine = create_engine(
                self.connection_string,
                echo=self.echo,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=self.pool_pre_ping
            )
            self._session_factory = scoped_session(
                sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
            )
            logger.info("Database engine created successfully")
        except Exception as e:
            logger.error(f"Error creating database engine: {e}")
            raise
    
    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine instance."""
        if not self._engine:
            self._create_engine()
        return self._engine
    
    @property
    def session_factory(self) -> scoped_session:
        """Get session factory."""
        if not self._session_factory:
            self._create_engine()
        return self._session_factory
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        Yields:
            Session: Database session
            
        Automatically handles commit/rollback and closing session on exit.
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tables(self) -> None:
        """Create all tables defined in models."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise


# SQLite connection string helper
def get_sqlite_connection_string(path: str = "indeed_jobs_local.sqlite3") -> str:
    """
    Get SQLite connection string for given path.
    
    Args:
        path: Path to SQLite database file
        
    Returns:
        SQLite connection string
    """
    return f"sqlite:///{path}"


# SQL Server connection helper
def get_sql_server_connection_string(
    server: str,
    database: str,
    driver: str = "ODBC Driver 17 for SQL Server",
    trusted_connection: bool = True,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> str:
    """
    Generate SQL Server connection string.
    
    Args:
        server: SQL Server host/instance name
        database: Database name
        driver: ODBC driver name
        trusted_connection: Use Windows authentication
        username: SQL Server login (used if trusted_connection is False)
        password: SQL Server password (used if trusted_connection is False)
        
    Returns:
        SQL Server connection string
    """
    driver_formatted = driver.replace(" ", "+")
    
    # Escape server name if it contains a single backslash but not a double backslash
    if '\\' in server and '\\\\' not in server:
        server = server.replace('\\', '\\\\')
    
    if trusted_connection:
        return f"mssql+pyodbc://{server}/{database}?driver={driver_formatted}&trusted_connection=yes"
    
    if username and password:
        return f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver_formatted}"
    
    raise ValueError("Either trusted_connection or username/password must be provided")


# Default database instance based on environment variables
def create_db_manager_from_env() -> DatabaseManager:
    """
    Create database manager from environment variables.
    
    Returns:
        Database manager instance
    
    Environment variables:
        DB_SQLITE_PATH: Path to SQLite database file
        DB_SERVER: SQL Server host/instance name
        DB_NAME: Database name
        DB_DRIVER: ODBC driver name
        DB_USERNAME: SQL Server login
        DB_PASSWORD: SQL Server password
        DB_USE_WINDOWS_AUTH: Use Windows authentication (true/false)
        SQLALCHEMY_ECHO: Echo SQL statements (true/false)
    """
    load_dotenv()
    
    # Determine connection string
    if os.getenv("DB_SQLITE_PATH"):
        connection_string = get_sqlite_connection_string(os.getenv("DB_SQLITE_PATH"))
        logger.info(f"Using SQLite connection: {connection_string}")
    else:
        server = os.getenv("DB_SERVER", "")
        database = os.getenv("DB_NAME", "IndeedJobs")
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
        use_windows_auth = os.getenv("DB_USE_WINDOWS_AUTH", "True").lower() in ('true', 'yes', '1', 't')
        
        if use_windows_auth:
            connection_string = get_sql_server_connection_string(server, database, driver)
        else:
            username = os.getenv("DB_USERNAME", "")
            password = os.getenv("DB_PASSWORD", "")
            connection_string = get_sql_server_connection_string(
                server, database, driver, 
                trusted_connection=False, 
                username=username, 
                password=password
            )
        logger.info(f"Using SQL Server connection to {server}/{database}")
    
    # Parse echo parameter
    echo = os.getenv("SQLALCHEMY_ECHO", "False").lower() in ('true', 'yes', '1')
    
    return DatabaseManager(connection_string, echo=echo)


# Create default database manager instance
db_manager = create_db_manager_from_env()

# Compatibility functions for existing code
def get_db_session() -> Session:
    """Get a database session from default manager."""
    return db_manager.get_session()


def init_db() -> None:
    """Initialize the database with required tables."""
    db_manager.create_tables()


def init_sqlite_db(path: str = "indeed_jobs_local.sqlite3") -> None:
    """
    Initialize a local SQLite database with the same schema.
    
    Args:
        path: Path to SQLite database file
    """
    sqlite_connection = get_sqlite_connection_string(path)
    sqlite_manager = DatabaseManager(sqlite_connection)
    sqlite_manager.create_tables() 