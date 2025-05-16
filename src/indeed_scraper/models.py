#!/usr/bin/env python3
"""Data models for Indeed scraper."""

import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union, ClassVar, Self, TypedDict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

class WorkSetting(str, Enum):
    """Work settings for job listings."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    IN_PERSON = "in-person"
    UNKNOWN = "unknown"

class JobType(str, Enum):
    """Job types for job listings."""
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    UNKNOWN = "unknown"

class SalaryPeriod(str, Enum):
    """Salary periods for job listings."""
    HOURLY = "hourly"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    UNKNOWN = "unknown"

class LocationInfo(TypedDict, total=False):
    """Structured location information."""
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    country: Optional[str]

class SalaryInfo(TypedDict, total=False):
    """Structured salary information."""
    min: Optional[float]
    max: Optional[float]
    period: Optional[str]
    min_yearly: Optional[float]
    max_yearly: Optional[float]
    midpoint_yearly: Optional[float]
    currency: Optional[str]

class JobListing(BaseModel):
    """Job listing data model with validation."""
    
    # Basic job information
    title: str
    company: str
    job_id: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    job_url: Optional[str] = None
    source: str = "Indeed"
    
    # Job details
    job_type: Optional[str] = None
    work_setting: Optional[str] = None
    
    # Timing information
    date_scraped: datetime = Field(default_factory=datetime.now)
    date_posted: Optional[str] = None
    
    # Search metadata
    search_url: Optional[str] = None
    queried_job_title: Optional[str] = None
    
    # Description (stored separately in database)
    description: Optional[str] = None
    
    # Processed salary fields
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_period: Optional[str] = None
    salary_min_yearly: Optional[float] = None
    salary_max_yearly: Optional[float] = None
    salary_midpoint_yearly: Optional[float] = None
    
    # Location components
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda v: v.isoformat()}
    )
    
    @field_validator('job_url')
    @classmethod
    def validate_job_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize job URL."""
        if not v:
            return None
            
        # Extract job ID if present and create normalized URL
        job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', v)
        if job_id_match:
            job_id = job_id_match.group(1)
            return f"https://www.indeed.com/viewjob?jk={job_id}"
        return v
    
    @field_validator('work_setting')
    @classmethod
    def validate_work_setting(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize work setting."""
        if not v:
            return None
        v_lower = str(v).lower()
        if 'remote' in v_lower:
            return WorkSetting.REMOTE
        elif 'hybrid' in v_lower:
            return WorkSetting.HYBRID
        elif v_lower and v_lower != 'unknown':
            return WorkSetting.IN_PERSON
        return v
    
    @model_validator(mode='after')
    def extract_job_id(self) -> Self:
        """Extract job_id from job_url if not already present."""
        if self.job_url and not self.job_id:
            job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', self.job_url)
            if job_id_match:
                self.job_id = job_id_match.group(1)
                
        return self
    
    @model_validator(mode='after')
    def calculate_salary_midpoint(self) -> Self:
        """Calculate salary midpoint if min and max yearly are available."""
        if self.salary_min_yearly is not None and self.salary_max_yearly is not None:
            self.salary_midpoint_yearly = (self.salary_min_yearly + self.salary_max_yearly) / 2
        elif self.salary_min_yearly is not None:
            self.salary_midpoint_yearly = self.salary_min_yearly
        elif self.salary_max_yearly is not None:
            self.salary_midpoint_yearly = self.salary_max_yearly
            
        return self
    
    def get_location_info(self) -> LocationInfo:
        """Get structured location information."""
        return {
            "city": self.city,
            "state": self.state,
            "zip": self.zip
        }
    
    def get_salary_info(self) -> SalaryInfo:
        """Get structured salary information."""
        return {
            "min": self.salary_min,
            "max": self.salary_max,
            "period": self.salary_period,
            "min_yearly": self.salary_min_yearly,
            "max_yearly": self.salary_max_yearly,
            "midpoint_yearly": self.salary_midpoint_yearly
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}

class ScrapeJob(BaseModel):
    """Configuration for a scrape job."""
    job_title: str
    location: Optional[str] = None
    search_radius: int = 25
    max_pages: int = 3
    days_ago: int = 7
    work_setting: Optional[str] = None
    job_type: Optional[str] = None
    
    model_config = ConfigDict(extra="allow")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScrapeJob':
        """Create a ScrapeJob from a dictionary."""
        return cls(**data) 