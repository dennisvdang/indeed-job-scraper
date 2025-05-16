#!/usr/bin/env python3
"""Base repository interface for job listings."""

import abc
from typing import List, Dict, Any, Optional, Set, Tuple, Protocol, Iterator, Generic, TypeVar
import pandas as pd

from ..models import JobListing

T = TypeVar('T')

class Repository(Protocol, Generic[T]):
    """Generic repository interface for any entity."""
    
    def save(self, entity: T) -> T:
        """Save a single entity."""
        ...
    
    def save_many(self, entities: List[T]) -> int:
        """Save multiple entities."""
        ...
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID."""
        ...
    
    def get_all(self) -> List[T]:
        """Get all entities."""
        ...
    
    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        ...


class JobListingRepositoryInterface(abc.ABC):
    """Abstract base class for job listing repositories."""
    
    @abc.abstractmethod
    def save_job_listing(self, job_listing: JobListing) -> JobListing:
        """
        Save a single job listing to storage.
        
        Args:
            job_listing: JobListing object to save
            
        Returns:
            The saved JobListing with any DB-generated fields updated
        """
        pass
    
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
    def get_job_listing(self, job_id: str) -> Optional[JobListing]:
        """
        Get a job listing by ID.
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            JobListing if found, None otherwise
        """
        pass
    
    @abc.abstractmethod
    def get_job_listings(
        self, 
        offset: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[JobListing]:
        """
        Get job listings with pagination and filtering.
        
        Args:
            offset: Starting offset for pagination
            limit: Maximum number of records to return
            filters: Dictionary of field:value pairs to filter by
            order_by: Field to order results by
            descending: Whether to sort in descending order
            
        Returns:
            List of job listings matching criteria
        """
        pass
    
    @abc.abstractmethod
    def get_job_listings_iterator(
        self,
        batch_size: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Iterator[JobListing]:
        """
        Get an iterator over job listings for efficient processing of large datasets.
        
        Args:
            batch_size: Number of records to fetch in each batch
            filters: Dictionary of field:value pairs to filter by
            
        Returns:
            Iterator yielding job listings
        """
        pass
    
    @abc.abstractmethod
    def count_job_listings(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count job listings matching filters.
        
        Args:
            filters: Dictionary of field:value pairs to filter by
            
        Returns:
            Count of matching job listings
        """
        pass
    
    @abc.abstractmethod
    def delete_job_listing(self, job_id: str) -> bool:
        """
        Delete a job listing.
        
        Args:
            job_id: ID of job listing to delete
            
        Returns:
            True if deleted, False if not found
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
    
    @abc.abstractmethod
    def get_job_listings_dataframe(
        self,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_description: bool = False
    ) -> pd.DataFrame:
        """
        Get job listings as a pandas DataFrame.
        
        Args:
            columns: List of columns to include (None for all)
            filters: Dictionary of field:value pairs to filter by
            include_description: Whether to include job descriptions
            
        Returns:
            DataFrame of job listings
        """
        pass
    
    @abc.abstractmethod
    def update_job_listing(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update fields for a job listing.
        
        Args:
            job_id: ID of job listing to update
            updates: Dictionary of field:value pairs to update
            
        Returns:
            True if updated, False if not found
        """
        pass 