"""Indeed Job Scraper - A tool for scraping, storing, and analyzing job listings."""

from importlib.metadata import version, PackageNotFoundError
from typing import Final, Dict, Any

try:
    __version__: Final[str] = version("indeed_scraper")
except PackageNotFoundError:
    __version__: Final[str] = "0.2.0"  # Default version

# Public API
from .models import JobListing, ScrapeJob, WorkSetting, JobType, SalaryPeriod
from .config import ScraperConfig
from .scraper import scrape_job_listings, run_scrape_job

__all__ = [
    "JobListing",
    "ScrapeJob", 
    "WorkSetting", 
    "JobType", 
    "SalaryPeriod",
    "ScraperConfig",
    "scrape_job_listings",
    "run_scrape_job",
] 