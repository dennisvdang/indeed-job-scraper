#!/usr/bin/env python3
"""Database repository implementation."""

from typing import List, Dict, Any, Optional, Set, Tuple, cast
import logging
import pandas as pd

from ..models import JobListing
from .base import JobListingRepositoryInterface
from database.repository import JobListingRepository as DBRepository
from ..logger import logger

class DBJobListingRepository(JobListingRepositoryInterface):
    """Repository that uses database backend."""
    
    def save_job_listings(self, job_listings: List[JobListing]) -> int:
        """
        Save job listings to database.
        
        Args:
            job_listings: List of job listings to save
            
        Returns:
            Number of job listings saved
        """
        try:
            # Convert pydantic models to dicts
            job_dicts = [job.dict(exclude_none=True) for job in job_listings]
            return DBRepository.save_job_listings(job_dicts)
        except Exception as e:
            logger.error(f"Error saving job listings: {e}")
            return 0
    
    def get_unique_values(self, field_name: str) -> List[Any]:
        """
        Get unique values for a field from the database.
        
        Args:
            field_name: Name of the field to get unique values for
            
        Returns:
            List of unique values
        """
        try:
            return DBRepository.get_unique_values(field_name)
        except Exception as e:
            logger.error(f"Error getting unique values for {field_name}: {e}")
            return []
    
    def check_job_ids_exist(self, job_ids: List[str]) -> Set[str]:
        """
        Check which job IDs already exist in the database.
        
        Args:
            job_ids: List of job IDs to check
            
        Returns:
            Set of job IDs that already exist
        """
        try:
            # Get all existing job IDs
            existing_job_ids = set(self.get_unique_values("job_id"))
            # Return intersection with provided job_ids
            return set(job_ids).intersection(existing_job_ids)
        except Exception as e:
            logger.error(f"Error checking job IDs: {e}")
            return set() 