#!/usr/bin/env python3
"""
Database Setup Script

This script initializes the database for Indeed Job Scraper.
It creates the database if it doesn't exist and sets up all required tables,
including job_descriptions.

Usage:
    python setup_database.py [--sqlite] [--sqlite-path SQLITE_PATH]

Example:
    python setup_database.py --sqlite --sqlite-path ./data/indeed_jobs.db
"""

import sys
from src.indeed_scraper.database.setup import main

if __name__ == "__main__":
    sys.exit(main()) 