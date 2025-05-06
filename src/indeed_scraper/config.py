#!/usr/bin/env python3
"""Configuration settings for Indeed job scraper."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class WorkSetting(str, Enum):
    """Work settings for job filtering."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"

class JobType(str, Enum):
    """Job types for filtering."""
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    TEMP_TO_HIRE = "temp-to-hire"

class ScraperConfig(BaseSettings):
    """Configuration for the Indeed job scraper."""
    
    # Browser settings
    headless: bool = Field(False, description="Run browser in headless mode")
    browser_timeout: int = Field(30, description="Browser timeout in seconds")
    captcha_detection_threshold: int = Field(2, description="Consecutive failures before captcha prompt")
    
    # Scraper settings
    default_search_radius: int = Field(25, description="Default search radius in miles")
    default_max_pages: int = Field(3, description="Default number of pages to scrape")
    default_days_ago: int = Field(7, description="Default days ago for job posting filter")
    min_delay_seconds: float = Field(1.0, description="Minimum delay between requests")
    max_delay_seconds: float = Field(3.0, description="Maximum delay between requests")
    valid_days_ago: List[int] = Field([1, 3, 7, 14], description="Valid options for days ago filter")
    
    # Database settings
    db_connection_string: Optional[str] = Field(None, description="Database connection string")
    
    # Add these fields that are being used from .env but weren't defined in the model
    db_server: Optional[str] = Field(None, description="Database server name")
    db_name: Optional[str] = Field(None, description="Database name")
    db_driver: Optional[str] = Field(None, description="Database driver")
    db_sqlite_path: Optional[str] = Field("data/indeed_jobs_local.sqlite3", description="SQLite database path")
    sqlalchemy_echo: Optional[str] = Field(None, description="Echo SQL statements")
    
    # Work setting filters
    work_setting_filters: Dict[str, str] = Field(
        {
            "remote": "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11",
            "hybrid": "&sc=0kf%3Aattr(DSQF7)%3B",
            "onsite": ""  # No specific filter for onsite/in-person
        },
        description="Work setting filters for Indeed URL"
    )
    
    # Job type filters
    job_type_filters: Dict[str, str] = Field(
        {
            "full-time": "&sc=0kf%3Aattr(CF3CP)%3B", 
            "part-time": "&sc=0kf%3Aattr(75GKK)%3B",
            "contract": "&sc=0kf%3Aattr(NJXCK)%3B",
            "temporary": "&sc=0kf%3Aattr(4HKF7)%3B",
            "temp-to-hire": "&sc=0kf%3Aattr(7SBAT)%3B"
        },
        description="Job type filters for Indeed URL"
    )
    
    # Selectors
    job_card_selector: str = Field(
        "div.job_seen_beacon, div.tapItem, [data-testid='jobListing']", 
        description="CSS selector for job cards"
    )
    next_page_selector: str = Field(
        "a[data-testid='pagination-page-next']",
        description="CSS selector for next page button"
    )
    
    model_config = SettingsConfigDict(
        env_prefix="INDEED_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow"  # Allow extra fields from env vars
    )

# Global configuration instance
config = ScraperConfig() 