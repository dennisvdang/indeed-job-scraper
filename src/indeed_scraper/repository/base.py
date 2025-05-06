#!/usr/bin/env python3
"""Base repository interface for job listings."""

import abc
from typing import List, Dict, Any, Optional, Set, Tuple
import pandas as pd

from ..models import JobListing

class JobListingRepositoryInterface(abc.ABC):
    """Abstract base class for job listing repositories."""
    
    @abc.abstractmethod
    def save_job_listings(self, job_listings: List[JobListing]) -> int:
        """
        Save multiple job listings to storage.
        
        Args:
            job_listings: List of JobListing objects to save
            
        Returns:
            Number of new listings saved
        """
        pass
    
    @abc.abstractmethod
    def get_unique_values(self, field_name: str) -> List[Any]:
        """
        Get unique values for a specific field.
        
        Args:
            field_name: Field name to get unique values for
            
        Returns:
            List of unique values
        """
        pass
    
    @abc.abstractmethod
    def check_job_ids_exist(self, job_ids: List[str]) -> Set[str]:
        """
        Check which job IDs already exist in storage.
        
        Args:
            job_ids: List of job IDs to check
            
        Returns:
            Set of job IDs that already exist
        """
        pass 