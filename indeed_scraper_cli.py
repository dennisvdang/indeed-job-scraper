#!/usr/bin/env python3
"""
CLI entry point for Indeed Job Scraper

This is a simple wrapper to run the scraper from the command line.
"""

import sys
from src.indeed_scraper import main

if __name__ == "__main__":
    sys.exit(main()) 