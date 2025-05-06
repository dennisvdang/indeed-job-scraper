"""Indeed Job Scraper package."""

from .models import JobListing, ScrapeJob, WorkSetting, JobType, SalaryPeriod
from .config import config

__version__ = "0.2.0"

__all__ = [
    "JobListing", 
    "ScrapeJob", 
    "WorkSetting", 
    "JobType", 
    "SalaryPeriod",
    "config"
] 