"""Data validation utilities for job listing data."""

from typing import Any, Optional
import re
import logging
import pandas as pd
from datetime import datetime

from .job_schema import (
    MAX_TITLE_LENGTH, MAX_COMPANY_LENGTH, MAX_LOCATION_LENGTH, MAX_URL_LENGTH,
    MAX_SOURCE_LENGTH, MAX_JOB_TYPE_LENGTH, MAX_WORK_SETTING_LENGTH,
    MAX_CITY_STATE_LENGTH, MAX_ZIP_LENGTH, MAX_PERIOD_LENGTH, MAX_JOB_ID_LENGTH,
    MAX_FLOAT_VALUE
)

logger = logging.getLogger(__name__)

def validate_and_clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean a DataFrame of job listings."""
    cleaned_df = df.copy().replace({pd.NA: None})
    
    # Handle column mappings and string fields
    column_mapping = {'salary': 'salary_original', 'zip': 'zip_code'}
    for old_col, new_col in column_mapping.items():
        if old_col in cleaned_df.columns and new_col not in cleaned_df.columns:
            cleaned_df[new_col] = cleaned_df[old_col]
            
    string_fields = {
        'job_id': MAX_JOB_ID_LENGTH, 'title': MAX_TITLE_LENGTH, 
        'company': MAX_COMPANY_LENGTH, 'location': MAX_LOCATION_LENGTH,
        'salary_original': MAX_TITLE_LENGTH, 'job_url': MAX_URL_LENGTH,
        'source': MAX_SOURCE_LENGTH, 'job_type': MAX_JOB_TYPE_LENGTH,
        'work_setting': MAX_WORK_SETTING_LENGTH, 'queried_job_title': MAX_TITLE_LENGTH,
        'city': MAX_CITY_STATE_LENGTH, 'state': MAX_CITY_STATE_LENGTH,
        'zip_code': MAX_ZIP_LENGTH, 'salary_period': MAX_PERIOD_LENGTH,
        'search_url': MAX_URL_LENGTH
    }
    
    for field, max_length in string_fields.items():
        if field in cleaned_df.columns and cleaned_df[field].dtype == 'object':
            cleaned_df[field] = cleaned_df[field].apply(
                lambda x: x[:max_length] if isinstance(x, str) and len(x) > max_length 
                else (None if isinstance(x, str) and not x.strip() else x)
            )
    
    # Process dates and numeric fields
    for field in ['date_scraped', 'date_posted']:
        if field in cleaned_df.columns:
            cleaned_df[field] = cleaned_df[field].apply(parse_date)
    
    if 'date_scraped' not in cleaned_df.columns or cleaned_df['date_scraped'].isnull().all():
        cleaned_df['date_scraped'] = datetime.now()
    
    numeric_fields = ['salary_min', 'salary_max', 'salary_min_yearly', 
                     'salary_max_yearly', 'salary_midpoint_yearly']
    
    for field in numeric_fields:
        if field in cleaned_df.columns:
            cleaned_df[field] = cleaned_df[field].apply(
                lambda x: clean_numeric_value(x, field)
            )
    
    # Set defaults
    if 'source' not in cleaned_df.columns:
        cleaned_df['source'] = 'Indeed'
    
    return cleaned_df

def parse_date(date_value: Any) -> Optional[datetime]:
    """Parse a date value from various formats to datetime."""
    if pd.isna(date_value) or date_value is None:
        return None
        
    if isinstance(date_value, datetime):
        return date_value
        
    if isinstance(date_value, str):
        date_str = date_value.strip()
        if not date_str:
            return None
            
        try:
            # ISO format first, then try common formats
            if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', 
                      '%Y/%m/%d', '%b %d, %Y', '%B %d, %Y']
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            logger.warning(f"Could not parse date: {date_str}")
            return None
                
        except Exception as e:
            logger.warning(f"Error parsing date {date_str}: {e}")
            return None
    
    logger.warning(f"Unsupported date format: {type(date_value)}")
    return None

def clean_numeric_value(value: Any, field_name: str) -> Optional[float]:
    """Clean and validate a numeric value."""
    if pd.isna(value) or value is None:
        return None
        
    try:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            value = re.sub(r'[^\d.-]', '', value)
            
        float_value = float(value)
        
        if float_value > MAX_FLOAT_VALUE:
            logger.warning(f"Capping {field_name} value from {float_value} to {MAX_FLOAT_VALUE}")
            float_value = MAX_FLOAT_VALUE
            
        return round(float_value, 2)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid numeric value for {field_name}: {value}, error: {e}")
        return None
        
def read_csv_with_validation(file_path: str) -> pd.DataFrame:
    """Read CSV file and perform initial validation."""
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        
        required_columns = ['job_id', 'title', 'company']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
            
        return validate_and_clean_dataframe(df)
    except Exception as e:
        logger.error(f"Error reading or validating CSV file {file_path}: {e}")
        raise 