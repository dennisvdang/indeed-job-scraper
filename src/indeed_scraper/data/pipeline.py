#!/usr/bin/env python3
"""Data processing pipeline for job listings."""

from typing import Dict, List, Optional, Union
import pandas as pd

from .cleaners import clean_descriptions, clean_string_field
from .transformers import (
    parse_locations, clean_locations, 
    extract_work_settings, clean_work_settings
)
from .enrichment import clean_salary_data

def clean_dataframe(df: pd.DataFrame, 
                   location_column: str = 'location', 
                   work_setting_column: str = 'work_setting',
                   salary_column: str = 'salary',
                   description_column: str = 'description') -> pd.DataFrame:
    """
    Clean job data including location, work setting, salary, and descriptions.
    
    Uses vectorized operations for better performance on large DataFrames.
    
    Args:
        df: Input DataFrame to clean
        location_column: Name of the location column
        work_setting_column: Name of the work setting column
        salary_column: Name of the salary column
        description_column: Name of the description column
        
    Returns:
        Cleaned and organized DataFrame
    """
    if df.empty:
        return df
        
    df = df.copy()
    
    # Clean string fields first
    for col in df.columns:
        if df[col].dtype == 'object' and col != description_column:
            df[col] = clean_string_field(df[col])
    
    # Clean location and extract components
    if location_column in df.columns:
        # Parse the location components first
        locations_df = parse_locations(df[location_column])
        
        # Add city, state, zip columns
        for col in ['city', 'state', 'zip']:
            df[col] = locations_df[col]
    
    # Clean work settings
    df = clean_work_settings(df, work_setting_column, location_column)
    
    # Clean salary data
    if salary_column in df.columns:
        df = clean_salary_data(df, salary_column)
    
    # Clean descriptions
    if description_column in df.columns and df[description_column].notna().any():
        df[description_column] = clean_descriptions(df[description_column])
    
    # Organize columns
    column_order = organize_columns(df, location_column, salary_column, description_column)
    all_cols = [col for col in column_order if col in df.columns]
    
    return df[all_cols]

def organize_columns(df: pd.DataFrame, 
                    location_column: str, 
                    salary_column: str,
                    description_column: str) -> list:
    """
    Organize columns in a logical order.
    
    Args:
        df: DataFrame to organize
        location_column: Name of location column
        salary_column: Name of salary column
        description_column: Name of description column
        
    Returns:
        List of column names in desired order
    """
    # Define column groupings
    id_cols = ['job_id', 'source']
    basic_info = ['title', 'company', location_column]
    job_details = ['job_type', 'work_setting']
    location_parsed = ['city', 'state', 'zip']
    salary_cols = [
        salary_column, 'salary_min', 'salary_max', 'salary_period',
        'salary_min_yearly', 'salary_max_yearly', 'salary_midpoint_yearly'
    ]
    url_cols = ['job_url', 'search_url']
    date_cols = ['date_posted', 'date_scraped']
    search_cols = ['queried_job_title']
    content_cols = [description_column]
    
    # Combine all columns
    all_cols = []
    for col_group in [id_cols, basic_info, job_details, location_parsed, 
                      salary_cols, url_cols, date_cols, search_cols, content_cols]:
        all_cols.extend(col_group)
    
    return all_cols 