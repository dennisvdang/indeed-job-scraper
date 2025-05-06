"""
Repository for job listing data operations.

This module provides functions to save and retrieve job listings from the database.
"""

from typing import List, Optional, Dict, Any, Tuple, Generator, TypeVar, Callable, Generic, ContextManager
from datetime import datetime
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd

from .job_schema import JobListing, JobDescription, ValidationError, MAX_FLOAT_VALUE
from .connection import get_db_session

# Configure logger
logger = logging.getLogger(__name__)

T = TypeVar('T')

def cap_and_round_salary(value: float) -> float:
    """Cap salary value at maximum allowed and round to 2 decimal places."""
    if value > MAX_FLOAT_VALUE:
        return round(MAX_FLOAT_VALUE, 2)
    return round(value, 2)

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

class JobListingRepository:
    """Repository for job listing data operations."""
    
    @staticmethod
    def _apply_filters(query, query_params: Dict[str, Any]):
        """Apply common filters to a query based on parameters."""
        for key, value in query_params.items():
            if value is None:
                continue
                
            if isinstance(value, list) and hasattr(JobListing, key):
                query = query.filter(getattr(JobListing, key).in_(value))
            elif hasattr(JobListing, key) and key not in ['date_posted_start', 'date_posted_end', 'has_salary']:
                query = query.filter(getattr(JobListing, key) == value)
        
        # Handle date range filter
        if 'date_posted_start' in query_params and 'date_posted_end' in query_params:
            start_date = query_params['date_posted_start']
            end_date = query_params['date_posted_end']
            
            if start_date and end_date:
                if not isinstance(start_date, datetime):
                    start_date = datetime.combine(start_date, datetime.min.time())
                if not isinstance(end_date, datetime):
                    end_date = datetime.combine(end_date, datetime.max.time())
                
                query = query.filter(JobListing.date_posted >= start_date)
                query = query.filter(JobListing.date_posted <= end_date)
        
        # Handle has_salary filter
        if query_params.get('has_salary'):
            query = query.filter(JobListing.salary_midpoint_yearly.isnot(None))
            
        return query
    
    @staticmethod
    def _process_job_dict(session: Session, job_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Process a single job dictionary, returning success status and error message."""
        try:
            # Check for valid job_id
            if 'job_id' not in job_dict or not job_dict['job_id']:
                return False, "Missing job_id"
            
            # Check if job already exists
            existing_job = session.query(JobListing).filter_by(job_id=job_dict['job_id']).first()
            if existing_job:
                logger.info(f"Job with ID {job_dict['job_id']} already exists, skipping")
                return False, "Job already exists"
            
            # Extract description for separate storage
            description = job_dict.pop('description', None)
            
            # Create job listing
            job = JobListing.from_dict(job_dict)
            session.add(job)
            
            # Add description if available
            if description:
                job_description = JobDescription(
                    job_id=job_dict['job_id'],
                    description=description
                )
                session.add(job_description)
            
            return True, ""
            
        except ValidationError as e:
            return False, f"Validation error: {e}"
        except Exception as e:
            return False, f"Error: {e}"
    
    @staticmethod
    def _merge_descriptions(df: pd.DataFrame, job_ids: List[str]) -> pd.DataFrame:
        """Merge job descriptions into the dataframe if available."""
        if df.empty or not job_ids:
            return df
            
        descriptions = JobListingRepository.get_job_descriptions(job_ids)
        if not descriptions.empty:
            df = df.merge(descriptions, on='job_id', how='left')
        
        return df
    
    @staticmethod
    def save_job_listings(job_dicts: List[Dict[str, Any]]) -> int:
        """
        Save multiple job listings to the database.
        
        Args:
            job_dicts: List of job listings as dictionaries
            
        Returns:
            Number of jobs saved
        """
        with session_scope() as session:
            added_count = 0
            error_count = 0
            
            for job_dict in job_dicts:
                success, error_message = JobListingRepository._process_job_dict(session, job_dict)
                if success:
                    added_count += 1
                else:
                    if "Job already exists" not in error_message:
                        error_count += 1
                        logger.error(f"Error with job ID {job_dict.get('job_id', 'unknown')}: {error_message}")
                
            logger.info(f"Saved {added_count} new job listings to database ({error_count} errors)")
            return added_count
    
    @staticmethod
    def get_all_job_listings() -> pd.DataFrame:
        """Get all job listings as a pandas DataFrame. """
        with session_scope() as session:
            try:
                jobs = session.query(JobListing).all()
                job_dicts = [job.to_dict() for job in jobs]
                df = pd.DataFrame(job_dicts)
                
                return JobListingRepository._merge_descriptions(df, [job.job_id for job in jobs])
            except Exception as e:
                logger.error(f"Error retrieving job listings: {e}")
                return pd.DataFrame()
    
    @staticmethod
    def get_job_listings_sample(limit: int = 500) -> pd.DataFrame:
        """
        Get a sample of job listings as a pandas DataFrame.
        
        Args:
            limit: Maximum number of job listings to return
            
        Returns:
            DataFrame containing the sample of job listings
        """
        with session_scope() as session:
            try:
                jobs = session.query(JobListing).limit(limit).all()
                job_dicts = [job.to_dict() for job in jobs]
                df = pd.DataFrame(job_dicts)
                
                return JobListingRepository._merge_descriptions(df, [job.job_id for job in jobs])
            except Exception as e:
                logger.error(f"Error retrieving job listings sample: {e}")
                return pd.DataFrame()
    
    @staticmethod
    def get_job_listings_by_query(query_params: Dict[str, Any]) -> pd.DataFrame:
        """
        Get job listings based on query parameters.
        
        Args:
            query_params: Dictionary of filter parameters
                - queried_job_title: List of job titles that were queried
                - state: List of states
                - work_setting: Work setting (remote, hybrid, in-person)
                - job_type: Job type (full-time, part-time, etc.)
                - has_salary: Boolean indicating whether to filter for jobs with salary data
                - date_posted_start: Start date for date_posted filter
                - date_posted_end: End date for date_posted filter
            
        Returns:
            DataFrame of filtered job listings
        """
        with session_scope() as session:
            try:
                query = session.query(JobListing)
                query = JobListingRepository._apply_filters(query, query_params)
                
                jobs = query.all()
                job_dicts = [job.to_dict() for job in jobs]
                df = pd.DataFrame(job_dicts)
                
                return JobListingRepository._merge_descriptions(df, [job.job_id for job in jobs])
            except Exception as e:
                logger.error(f"Error querying job listings: {e}")
                return pd.DataFrame()
    
    @staticmethod
    def get_unique_values(column_name: str) -> List[Any]:
        """
        Get unique values for a specific column.
        
        Args:
            column_name: Name of the column to get unique values from
            
        Returns:
            List of unique values in the column
        """
        with session_scope() as session:
            try:
                if not hasattr(JobListing, column_name):
                    return []
                    
                column = getattr(JobListing, column_name)
                # Query distinct values, excluding None/NULL
                results = session.query(column).filter(column.isnot(None)).distinct().all()
                return [r[0] for r in results]
            except Exception as e:
                logger.error(f"Error getting unique values for {column_name}: {e}")
                return []
    
    @staticmethod
    def get_job_count() -> int:
        """Get total number of job listings in database."""
        with session_scope() as session:
            try:
                return session.query(func.count(JobListing.id)).scalar() or 0
            except Exception as e:
                logger.error(f"Error counting job listings: {e}")
                return 0
            
    @staticmethod
    def save_from_dataframe(df: pd.DataFrame) -> Tuple[int, int]:
        """
        Save job listings from a pandas DataFrame.
        
        Args:
            df: DataFrame containing job listings data
            
        Returns:
            Tuple of (number of jobs saved, number of errors)
        """
        job_dicts = df.to_dict(orient='records')
        with session_scope() as session:
            added_count = 0
            error_count = 0
            
            for job_dict in job_dicts:
                try:
                    # Clean NaN values first
                    cleaned_dict = {k: (None if pd.isna(v) else v) for k, v in job_dict.items()}
                    
                    # Process the cleaned dictionary
                    success, error_message = JobListingRepository._process_job_dict(session, cleaned_dict)
                    if success:
                        added_count += 1
                    else:
                        if "Job already exists" not in error_message:
                            error_count += 1
                            logger.error(f"Error processing job: {error_message}")
                        
                except Exception as e:
                    logger.error(f"Error processing job: {e}")
                    error_count += 1
                
            logger.info(f"Saved {added_count} jobs from DataFrame ({error_count} errors)")
            return added_count, error_count
            
    @staticmethod
    def get_job_descriptions(job_ids: List[str]) -> pd.DataFrame:
        """
        Get job descriptions for the specified job IDs.
        
        Args:
            job_ids: List of job IDs to fetch descriptions for
            
        Returns:
            DataFrame with job_id and description columns
        """
        if not job_ids:
            return pd.DataFrame()
            
        with session_scope() as session:
            try:
                descriptions = session.query(JobDescription).filter(JobDescription.job_id.in_(job_ids)).all()
                
                if descriptions:
                    desc_dicts = [{'job_id': desc.job_id, 'description': desc.description} for desc in descriptions]
                    return pd.DataFrame(desc_dicts)
                return pd.DataFrame()
            except Exception as e:
                logger.error(f"Error retrieving job descriptions: {e}")
                return pd.DataFrame()
            
    @staticmethod
    def get_description_for_job(job_id: str) -> Optional[str]:
        """
        Get job description for a specific job ID.
        
        Args:
            job_id: Job ID to fetch the description for
            
        Returns:
            Job description text or None if not found
        """
        with session_scope() as session:
            try:
                description = session.query(JobDescription).filter_by(job_id=job_id).first()
                return description.description if description else None
            except Exception as e:
                logger.error(f"Error retrieving job description for {job_id}: {e}")
                return None

    @staticmethod
    def get_paginated_job_listings(
        page: int = 0, 
        items_per_page: int = 20,
        query_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[pd.DataFrame, int]:
        """
        Get a paginated list of job listings.
        
        Args:
            page: Page number (0-indexed)
            items_per_page: Number of items per page
            query_params: Optional filter parameters
            
        Returns:
            Tuple of (DataFrame of job listings without descriptions, total count of matching records)
        """
        with session_scope() as session:
            try:
                query = session.query(JobListing)
                
                if query_params:
                    query = JobListingRepository._apply_filters(query, query_params)
                
                total_count = query.count()
                
                query = query.order_by(JobListing.id)
                query = query.offset(page * items_per_page).limit(items_per_page)
                
                jobs = query.all()
                job_dicts = [job.to_dict() for job in jobs]
                df = pd.DataFrame(job_dicts)
                
                return df, total_count
            except Exception as e:
                logger.error(f"Error querying paginated job listings: {e}")
                return pd.DataFrame(), 0

    @staticmethod
    def get_job_details(job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete details for a specific job including its description.
        
        Args:
            job_id: The unique identifier of the job
            
        Returns:
            Dictionary with job details and description, or None if not found
        """
        with session_scope() as session:
            try:
                # Get job listing
                job = session.query(JobListing).filter_by(job_id=job_id).first()
                if not job:
                    return None
                    
                job_dict = job.to_dict()
                
                # Get description separately
                description = session.query(JobDescription).filter_by(job_id=job_id).first()
                if description:
                    job_dict['description'] = description.description
                
                return job_dict
            except Exception as e:
                logger.error(f"Error retrieving job details for {job_id}: {e}")
                return None 