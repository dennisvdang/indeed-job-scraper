"""
SQL Server database setup script.

This script creates the database and initializes tables required for the Indeed Job Scraper.
"""

from typing import Optional
import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path so we can import database modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set default server details
DEFAULT_SERVER = "DESKTOP-7HOBVL1\\SQLEXPRESS"
DEFAULT_DATABASE = "IndeedJobs"
DEFAULT_DRIVER = "ODBC Driver 17 for SQL Server"

def create_database(
    server: str = DEFAULT_SERVER,
    database: str = DEFAULT_DATABASE,
    username: Optional[str] = None,
    password: Optional[str] = None,
    driver: str = DEFAULT_DRIVER
) -> bool:
    """
    Create the SQL Server database if it doesn't exist.
    
    Args:
        server: SQL Server instance
        database: Database name
        username: SQL Server username (if using SQL authentication)
        password: SQL Server password (if using SQL authentication)
        driver: ODBC driver to use
        
    Returns:
        True if database creation was successful, False otherwise
    """
    try:
        import pyodbc
    except ImportError:
        logger.error("pyodbc package is required for database setup")
        return False
    
    # Fix escaping in server name
    if '\\' in server and '\\\\' not in server:
        server = server.replace('\\', '\\\\')
    
    # Determine connection string based on authentication method
    try:
        if username and password:
            # SQL Server authentication
            conn_str = f"DRIVER={{{driver}}};SERVER={server};UID={username};PWD={password}"
        else:
            # Windows authentication
            conn_str = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes"
        
        logger.info(f"Connecting to SQL Server at {server}")
        # Connect to SQL Server
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT DB_ID('{database}')")
        db_id = cursor.fetchone()[0]
        
        if db_id is None:
            logger.info(f"Creating database '{database}'...")
            cursor.execute(f"CREATE DATABASE {database}")
            logger.info(f"Database '{database}' created successfully.")
        else:
            logger.info(f"Database '{database}' already exists.")
        
        # Close connection
        cursor.close()
        conn.close()
        return True
        
    except pyodbc.Error as e:
        logger.error(f"Error connecting to SQL Server: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def update_connection_file() -> None:
    """
    Update the connection.py file with the correct connection string.
    """
    try:
        connection_file = Path(__file__).parent / "connection.py"
        with open(connection_file, "r") as f:
            content = f.read()
        
        # Replace the default connection string
        if "DEFAULT_CONNECTION_STRING" in content:
            server_escaped = DEFAULT_SERVER.replace("\\", "\\\\")
            driver_escaped = DEFAULT_DRIVER.replace(" ", "+")
            new_conn_string = f'DEFAULT_CONNECTION_STRING = "mssql+pyodbc://{server_escaped}/{DEFAULT_DATABASE}?driver={driver_escaped}&trusted_connection=yes'
            
            new_content = content.replace(
                'DEFAULT_CONNECTION_STRING = "',
                new_conn_string
            )
            
            with open(connection_file, "w") as f:
                f.write(new_content)
            
            logger.info("Updated connection.py with the correct connection string")
    except Exception as e:
        logger.error(f"Error updating connection file: {e}")

def init_database_schema() -> bool:
    """
    Initialize the database schema with required tables.
    
    Returns:
        True if schema initialization was successful, False otherwise
    """
    try:
        # First make sure connection.py has the right connection string
        update_connection_file()
        
        from src.database.connection import init_db
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database tables created successfully.")
        return True
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")
        return False

def main() -> int:
    """
    Main entry point for database setup.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Set up Indeed Jobs database")
    parser.add_argument("--server", help="SQL Server instance name or IP")
    parser.add_argument("--database", help="Database name")
    parser.add_argument("--username", help="SQL Server username (if using SQL authentication)")
    parser.add_argument("--password", help="SQL Server password (if using SQL authentication)")
    parser.add_argument("--driver", help="ODBC Driver name")
    
    args = parser.parse_args()
    
    # Load environment variables (but prefer hardcoded defaults)
    load_dotenv()
    
    # Get parameters from args, environment variables, or use defaults
    server = args.server or os.getenv("DB_SERVER", DEFAULT_SERVER)
    database = args.database or os.getenv("DB_NAME", DEFAULT_DATABASE)
    username = args.username or os.getenv("DB_USERNAME")
    password = args.password or os.getenv("DB_PASSWORD")
    driver = args.driver or os.getenv("DB_DRIVER", DEFAULT_DRIVER)
    
    # Create database
    if not create_database(server, database, username, password, driver):
        return 1
    
    # Initialize database schema
    if not init_database_schema():
        return 1
    
    logger.info("Database setup complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 