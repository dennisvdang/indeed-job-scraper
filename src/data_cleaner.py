#!/usr/bin/env python3
"""Utility for cleaning Indeed job data including location, work setting, and salary."""

import re
from pathlib import Path
from typing import Dict, Optional, Union
from datetime import datetime

import pandas as pd


# =====================
# Location Processing
# =====================
def parse_location(location: str) -> Dict[str, Optional[str]]:
    """Parse a location string into city, state, and zip components."""
    components = {
        'city': None,
        'state': None,
        'zip': None,
        'full_location': location
    }
    
    if not isinstance(location, str) or not location:
        return components
    
    match = re.search(r'([^,]+),\s*([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?', location)
    if match:
        components['city'] = match.group(1).strip()
        components['state'] = match.group(2).strip()
        if match.group(3):
            components['zip'] = match.group(3).strip()
    
    return components


def clean_location(location: str) -> Optional[str]:
    """Clean job location to standardized City, State ZIP format."""
    if not isinstance(location, str) or not location:
        return None
    
    # Handle remote positions
    if re.match(r'^remote\b', location, re.IGNORECASE):
        remote_match = re.search(r'remote\s+in\s+(.*)', location, re.IGNORECASE)
        return remote_match.group(1).strip() if remote_match else "Remote"
    
    # Extract location after "in" preposition
    in_match = re.search(r'\sin\s+(.*)', location, re.IGNORECASE)
    if in_match:
        location = in_match.group(1).strip()
    
    # Clean up location text
    location = re.sub(r'\(.*?\)', '', location)                      # Remove parentheticals
    location = re.sub(r'\+\d+\s+locations?', '', location, flags=re.IGNORECASE)  # Remove "+X locations"
    location = re.sub(r',\s*United States$', '', location)           # Remove ", United States"
    location = re.sub(r'\s+', ' ', location).strip()                 # Normalize whitespace
    
    # Extract city, state, zip
    match = re.search(r'([^,]+),\s*([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?', location)
    if match:
        city = match.group(1).strip()
        state = match.group(2).strip()
        zip_code = match.group(3).strip() if match.group(3) else ""
        
        return f"{city}, {state} {zip_code}" if zip_code else f"{city}, {state}"
    
    return location


# =====================
# Work Setting Processing
# =====================
def extract_work_setting(text: str) -> Optional[str]:
    """Extract work setting (remote, hybrid) from text."""
    if not isinstance(text, str) or not text:
        return None
        
    text_lower = text.lower()
    if "remote" in text_lower:
        return "remote"
    elif "hybrid" in text_lower:
        return "hybrid"
    
    return None


def clean_work_setting(df: pd.DataFrame, work_setting_column: str = 'work_setting', 
                       location_column: str = 'location') -> pd.DataFrame:
    """Clean work setting data and fill missing values based on location."""
    df = df.copy()
    if work_setting_column not in df.columns:
        df[work_setting_column] = None
    
    # Extract work setting from location when missing
    if location_column in df.columns:
        mask = df[work_setting_column].isna() | (df[work_setting_column] == '')
        loc_mask = mask & df[location_column].notna()
        
        if loc_mask.any():
            df.loc[loc_mask, 'temp_setting'] = df.loc[loc_mask, location_column].apply(extract_work_setting)
            update_mask = df['temp_setting'].notna()
            if update_mask.any():
                df.loc[update_mask, work_setting_column] = df.loc[update_mask, 'temp_setting']
            df = df.drop('temp_setting', axis=1)
    
    # Apply priority rules for work setting types
    for pattern, setting in [('remote', 'remote'), ('hybrid', 'hybrid')]:
        mask = df[work_setting_column].astype(str).str.contains(pattern, case=False, na=False)
        df.loc[mask, work_setting_column] = setting
    
    # Check for remote mentions in location field
    if location_column in df.columns:
        remote_in_location = df[location_column].astype(str).str.contains('remote', case=False, na=False)
        df.loc[remote_in_location, work_setting_column] = 'remote'
    
    # Set remaining values as in-person
    non_remote_hybrid = ~df[work_setting_column].isin(['remote', 'hybrid']) & df[work_setting_column].notna() & (df[work_setting_column] != '')
    df.loc[non_remote_hybrid, work_setting_column] = 'in-person'
    df[work_setting_column] = df[work_setting_column].fillna('in-person')
    
    return df


# =====================
# Salary Processing
# =====================
def parse_salary(salary_text: str) -> Dict[str, Optional[float]]:
    """Parse salary text into min, max, and period components."""
    result = {
        'salary_min': None,
        'salary_max': None,
        'salary_period': None,
        'salary_original': salary_text
    }
    
    if not isinstance(salary_text, str) or not salary_text:
        return result
    
    # Find all dollar amounts
    amounts = re.findall(r'\$?([\d,]+\.?\d*)', salary_text)
    if not amounts:
        return result
    
    # Convert amounts to floats
    amounts = [float(amt.replace(',', '')) for amt in amounts]
    
    # Determine payment period
    text_lower = salary_text.lower()
    if 'hour' in text_lower:
        result['salary_period'] = 'hourly'
    elif 'week' in text_lower:
        result['salary_period'] = 'weekly'
    elif 'month' in text_lower:
        result['salary_period'] = 'monthly'
    else:
        result['salary_period'] = 'yearly'
    
    # Set min and max values
    if len(amounts) >= 2:
        result['salary_min'] = min(amounts)
        result['salary_max'] = max(amounts)
    elif amounts:
        result['salary_min'] = result['salary_max'] = amounts[0]
    
    return result


def standardize_salary(parsed_salary: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Standardize salary to yearly values for comparison."""
    result = parsed_salary.copy()
    
    min_salary = parsed_salary['salary_min']
    period = parsed_salary['salary_period']
    
    if min_salary is None or period is None:
        return result
    
    # Conversion multipliers to yearly
    conversions = {
        'hourly': 40 * 52,  # 40 hours/week, 52 weeks/year
        'weekly': 52,       # 52 weeks/year
        'monthly': 12,      # 12 months/year
        'yearly': 1
    }
    
    multiplier = conversions.get(period, 1)
    result['salary_min_yearly'] = min_salary * multiplier
    
    if parsed_salary['salary_max'] is not None:
        result['salary_max_yearly'] = parsed_salary['salary_max'] * multiplier
    
    return result


def clean_salary_data(df: pd.DataFrame, salary_column: str = 'salary') -> pd.DataFrame:
    """Extract and standardize salary information from raw salary text."""
    if salary_column not in df.columns:
        return df
    
    df = df.copy()
    
    # Parse and standardize all salaries
    parsed_salaries = df[salary_column].apply(parse_salary)
    standardized = parsed_salaries.apply(standardize_salary)
    
    # Extract components
    df['salary_min'] = parsed_salaries.apply(lambda x: x['salary_min'])
    df['salary_max'] = parsed_salaries.apply(lambda x: x['salary_max'])
    df['salary_period'] = parsed_salaries.apply(lambda x: x['salary_period'])
    df['salary_min_yearly'] = standardized.apply(lambda x: x.get('salary_min_yearly'))
    df['salary_max_yearly'] = standardized.apply(lambda x: x.get('salary_max_yearly'))
    
    # Calculate salary midpoint for analysis
    df['salary_midpoint_yearly'] = df.apply(
        lambda row: ((row['salary_min_yearly'] or 0) + (row['salary_max_yearly'] or 0)) / 2
        if pd.notna(row['salary_min_yearly']) and pd.notna(row['salary_max_yearly']) 
        else None, 
        axis=1
    )
    
    return df


# =====================
# Main Cleaning Functions
# =====================
def clean_dataframe(df: pd.DataFrame, 
                    location_column: str = 'location', 
                    work_setting_column: str = 'work_setting',
                    salary_column: str = 'salary',
                    description_column: str = 'description') -> pd.DataFrame:
    """
    Clean job data including location, work setting, salary, and dates.
    
    Args:
        df: Input DataFrame to clean
        location_column: Name of the location column
        work_setting_column: Name of the work setting column
        salary_column: Name of the salary column
        description_column: Name of the description column
        
    Returns:
        Cleaned and organized DataFrame
    """
    df = df.copy()
    
    # Clean location and work setting
    if location_column in df.columns:
        # Handle work setting first (uses original location data)
        df = clean_work_setting(df, work_setting_column, location_column)
        df[location_column] = df[location_column].apply(clean_location)
        
        # Extract location components
        location_components = df[location_column].apply(parse_location).tolist()
        location_df = pd.DataFrame(location_components)
        for col in ['city', 'state', 'zip']:
            if col in location_df.columns:
                df[col] = location_df[col]
    
    # Clean salary data
    if salary_column in df.columns:
        df = clean_salary_data(df, salary_column)
    
    # Rename description column
    if description_column in df.columns and description_column != 'job_description':
        df = df.rename(columns={description_column: 'job_description'})
    
    # Organize columns for better readability
    column_order = organize_columns(df, location_column, salary_column, description_column)
    
    return df[column_order]


def organize_columns(df: pd.DataFrame, 
                    location_column: str, 
                    salary_column: str,
                    description_column: str) -> list:
    """Organize DataFrame columns into a logical order."""
    # Define column groups for ordering
    column_groups = {
        'id': ['job_id', 'source', 'is_ad'],
        'essentials': ['title', 'company', 'work_setting', 'job_type'],
        'dates': ['date_posted', 'date_scraped'],
        'location': ['city', 'state', 'zip'],
        'compensation': ['salary_period', 'salary_min', 'salary_max', 
                        'salary_min_yearly', 'salary_max_yearly', 'salary_midpoint_yearly'],
        'urls': ['job_url', 'search_url'],
        'text': ['job_description']
    }
    
    # Get all columns in specified order
    ordered_columns = [col for group in column_groups.values() 
                      for col in group if col in df.columns]
    
    # Columns to exclude from the "other" category
    excludes = [location_column, salary_column]
    if description_column != 'job_description':
        excludes.append(description_column)
    
    # Add any remaining columns not in ordered groups
    remaining = [col for col in df.columns 
                if col not in ordered_columns and col not in excludes]
    ordered_columns.extend(remaining)
    
    return ordered_columns 