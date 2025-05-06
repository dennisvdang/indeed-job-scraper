#!/usr/bin/env python3
"""
Database Setup Script

This script initializes the database for Indeed Job Scraper.
It creates the database if it doesn't exist and sets up all required tables,
including the job_descriptions table.

Usage:
    python -m src.indeed_scraper.database.setup [--sqlite-path SQLITE_PATH]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

from ..config import config
from ...database.connection import get_db_session, init_db, init_sqlite_db
from ...database.job_schema import JobListing, JobDescription, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("db_setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_database(use_sqlite: bool = False, sqlite_path: Optional[str] = None) -> bool:
    """
    Initialize the database schema with required tables.
    
    Args:
        use_sqlite: Whether to use SQLite instead of SQL Server
        sqlite_path: Path to SQLite database file (if using SQLite)
        
    Returns:
        True if initialization was successful, False otherwise
    """
    try:
        if sqlite_path:
            os.environ["DB_SQLITE_PATH"] = sqlite_path
            
        if use_sqlite or sqlite_path:
            logger.info(f"Initializing SQLite database{f' at {sqlite_path}' if sqlite_path else ''}")
            init_sqlite_db()
        else:
            logger.info("Initializing SQL Server database")
            init_db()
            
        logger.info("Database tables created successfully.")
        return True
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")
        return False

def setup_job_descriptions_table() -> bool:
    """
    Set up the job_descriptions table if it doesn't exist.
    
    Returns:
        True if successful, False otherwise
    """
    session = get_db_session()
    try:
        # Get SQLAlchemy engine from session
        engine = session.get_bind()
        
        # Check if the table already exists
        inspector = inspect(engine)
        if 'job_descriptions' in inspector.get_table_names():
            logger.info("job_descriptions table already exists")
            return True
        
        # Create the table
        JobDescription.__table__.create(engine, checkfirst=True)
        logger.info("Successfully created job_descriptions table")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error creating job_descriptions table: {e}")
        return False
    finally:
        session.close()

def migrate_descriptions() -> bool:
    """
    Migrate descriptions from job_listings to job_descriptions table.
    
    Returns:
        True if successful or not needed, False on error
    """
    session = get_db_session()
    try:
        # Check if description column exists in job_listings table
        inspector = inspect(session.get_bind())
        has_desc_column = False
        for column in inspector.get_columns('job_listings'):
            if column['name'] == 'description':
                has_desc_column = True
                break
        
        if not has_desc_column:
            logger.info("No description column found in job_listings table. Migration not needed.")
            return True
        
        # Query all jobs with descriptions
        query = """
        SELECT job_id, description 
        FROM job_listings 
        WHERE description IS NOT NULL AND job_id IS NOT NULL
        """
        result = session.execute(text(query))
        
        # Migrate data
        count = 0
        for row in result:
            # Check if description already exists in job_descriptions
            existing = session.query(JobDescription).filter_by(job_id=row.job_id).first()
            if existing:
                logger.debug(f"Description for job {row.job_id} already exists, skipping")
                continue
                
            # Create new description record
            desc = JobDescription(job_id=row.job_id, description=row.description)
            session.add(desc)
            count += 1
            
            # Commit in batches to avoid memory issues
            if count % 100 == 0:
                session.commit()
                logger.info(f"Migrated {count} descriptions so far")
        
        # Final commit
        session.commit()
        logger.info(f"Successfully migrated {count} descriptions to job_descriptions table")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error migrating descriptions: {e}")
        return False
    finally:
        session.close()

def main() -> int:
    """
    Main entry point for database setup.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Set up Indeed Jobs database")
    parser.add_argument("--sqlite", action="store_true", help="Use SQLite instead of SQL Server")
    parser.add_argument("--sqlite-path", help="Path to SQLite database file")
    
    args = parser.parse_args()
    use_sqlite = args.sqlite
    sqlite_path = args.sqlite_path
    
    # Initialize database
    if not init_database(use_sqlite, sqlite_path):
        return 1
    
    # Set up job descriptions table
    if not setup_job_descriptions_table():
        logger.error("Failed to create job_descriptions table. Aborting upgrade.")
        return 1
    
    # Migrate existing descriptions if needed
    if not migrate_descriptions():
        logger.error("Failed to migrate descriptions. Aborting upgrade.")
        return 1
    
    logger.info("Database setup complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 