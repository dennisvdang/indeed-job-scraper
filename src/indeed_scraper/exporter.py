#!/usr/bin/env python3
"""Export job listings to database or file."""

from typing import List, Dict, Optional, Any
from pathlib import Path
import pandas as pd

from .models import JobListing
from .logger import logger
from .repository.base import JobListingRepositoryInterface
from .data import clean_dataframe

def export_jobs_to_db(
    jobs: List[JobListing],
    repository: JobListingRepositoryInterface
) -> int:
    """
    Export job listings to database.
    
    Args:
        jobs: List of JobListing objects to export
        repository: Repository to save the jobs to
        
    Returns:
        Number of jobs successfully saved
    """
    if not jobs:
        logger.warning("No jobs to save")
        return 0
    
    try:
        # First clean the job data using the data preprocessing pipeline
        df = pd.DataFrame([job.dict() for job in jobs])
        
        try:
            logger.info("Cleaning data...")
            df = clean_dataframe(
                df,
                location_column='location',
                work_setting_column='work_setting',
                salary_column='salary',
                description_column='description'
            )
        except Exception as e:
            logger.error(f"Data cleaning error: {e}")
            logger.info("Continuing with original job data")
        
        # Convert data back to JobListing objects
        cleaned_jobs = []
        for _, row in df.iterrows():
            cleaned_dict = {k: v for k, v in row.to_dict().items() 
                           if not (pd.isna(v) if isinstance(v, float) else False)}
            
            cleaned_jobs.append(JobListing(**cleaned_dict))
        
        # Filter for jobs with both salary and description
        filtered_jobs = [job for job in cleaned_jobs if job.salary and job.description]
        
        if not filtered_jobs:
            logger.warning("No jobs with both salary and description to save")
            return 0
            
        # Save to database
        saved_count = repository.save_job_listings(filtered_jobs)
        logger.info(f"Saved {saved_count} jobs to database")
        return saved_count
        
    except Exception as e:
        logger.error(f"Error exporting jobs to database: {e}")
        return 0

def export_jobs_to_csv(
    jobs: List[JobListing],
    output_file: str,
    include_description: bool = True
) -> bool:
    """
    Export job listings to CSV file.
    
    Args:
        jobs: List of JobListing objects to export
        output_file: Path to output CSV file
        include_description: Whether to include descriptions in the output
        
    Returns:
        True if export was successful, False otherwise
    """
    if not jobs:
        logger.warning("No jobs to export")
        return False
    
    try:
        # Convert to DataFrame for export
        df = pd.DataFrame([job.dict() for job in jobs])
        
        # Apply data cleaning
        try:
            logger.info("Cleaning data before CSV export...")
            df = clean_dataframe(
                df,
                location_column='location',
                work_setting_column='work_setting',
                salary_column='salary',
                description_column='description'
            )
        except Exception as e:
            logger.error(f"Data cleaning error: {e}")
            logger.info("Continuing with original job data")
        
        # Remove description if not included
        if not include_description and 'description' in df.columns:
            df = df.drop('description', axis=1)
        
        # Create output directory if it doesn't exist
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export to CSV
        df.to_csv(output_file, index=False, encoding='utf-8')
        logger.info(f"Exported {len(df)} jobs to {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error exporting jobs to CSV: {e}")
        return False 