#!/usr/bin/env python3
"""Data transformation utilities for job listings."""

import re
import numpy as np
import pandas as pd
from typing import Dict, Optional, List

# Pre-compile regular expressions for better performance
LOCATION_PATTERN = re.compile(r'([^,]+),\s*([A-Z]{2})(?:\s+(\d{5}(?:-\d{4})?))?')
REMOTE_PATTERN = re.compile(r'^remote\b', re.IGNORECASE)
REMOTE_IN_PATTERN = re.compile(r'remote\s+in\s+(.*)', re.IGNORECASE)
IN_PREPOSITION_PATTERN = re.compile(r'\sin\s+(.*)', re.IGNORECASE)
PARENTHESIS_PATTERN = re.compile(r'\(.*?\)')
MULTI_LOCATION_PATTERN = re.compile(r'\+\d+\s+locations?', re.IGNORECASE)
US_SUFFIX_PATTERN = re.compile(r',\s*United States$')
WHITESPACE_PATTERN = re.compile(r'\s+')

def parse_locations(locations: pd.Series) -> pd.DataFrame:
    """
    Vectorized parsing of location strings into city, state, and zip components.
    
    Args:
        locations: Series of location strings
        
    Returns:
        DataFrame with parsed location components
    """
    # Create DataFrame with NaN values 
    result = pd.DataFrame({
        'city': pd.Series(dtype='object'),
        'state': pd.Series(dtype='object'),
        'zip': pd.Series(dtype='object'),
        'full_location': locations
    })
    
    # Extract components with vectorized operations
    valid_mask = locations.notna() & locations.astype(str).str.strip().str.len().gt(0)
    if valid_mask.any():
        # Apply regex extraction vectorized
        extracted = locations[valid_mask].str.extract(LOCATION_PATTERN)
        
        if not extracted.empty:
            result.loc[valid_mask, 'city'] = extracted[0].str.strip()
            result.loc[valid_mask, 'state'] = extracted[1].str.strip()
            result.loc[valid_mask, 'zip'] = extracted[2].str.strip()
    
    return result

def clean_locations(locations: pd.Series) -> pd.Series:
    """
    Vectorized cleaning of job locations to standardized format.
    
    Args:
        locations: Series of location strings
        
    Returns:
        Series of cleaned location strings
    """
    # Handle NaN and empty strings
    if locations.isna().all():
        return locations
    
    # Convert to string type and make a copy
    loc_series = locations.astype(str).copy()
    
    # Handle remote positions
    remote_mask = loc_series.str.match(REMOTE_PATTERN)
    remote_in_matches = loc_series[remote_mask].str.extract(REMOTE_IN_PATTERN)
    remote_locations = pd.Series(index=remote_in_matches.index, dtype='object')
    remote_locations.loc[remote_in_matches[0].notna()] = remote_in_matches[0].str.strip()
    remote_locations.fillna("Remote", inplace=True)
    
    # For non-remote locations
    non_remote_mask = ~remote_mask
    if non_remote_mask.any():
        # Extract location after "in" preposition
        in_matches = loc_series[non_remote_mask].str.extract(IN_PREPOSITION_PATTERN)
        in_mask = in_matches[0].notna()
        if in_mask.any():
            loc_series.loc[non_remote_mask.index[in_mask]] = in_matches[0][in_mask].str.strip()
        
        # Clean up location text using vectorized operations
        loc_series = loc_series.str.replace(PARENTHESIS_PATTERN, '', regex=True)
        loc_series = loc_series.str.replace(MULTI_LOCATION_PATTERN, '', regex=True)
        loc_series = loc_series.str.replace(US_SUFFIX_PATTERN, '', regex=True)
        loc_series = loc_series.str.replace(WHITESPACE_PATTERN, ' ', regex=True).str.strip()
        
        # Extract city, state, zip format
        location_parts = loc_series.str.extract(LOCATION_PATTERN)
        location_mask = location_parts[0].notna() & location_parts[1].notna()
        
        # Format as City, State ZIP where components exist
        formatted_locations = pd.Series(index=loc_series.index, dtype='object')
        
        if location_mask.any():
            city_state = location_parts[0][location_mask].str.strip() + ", " + location_parts[1][location_mask].str.strip()
            
            # Add ZIP where available
            zip_mask = location_parts[2].notna() & location_mask
            formatted_locations.loc[location_mask] = city_state
            
            if zip_mask.any():
                formatted_locations.loc[zip_mask] = city_state[zip_mask] + " " + location_parts[2][zip_mask].str.strip()
            
            # Use original for those that didn't match pattern
            non_match_mask = ~location_mask & non_remote_mask
            if non_match_mask.any():
                formatted_locations.loc[non_match_mask] = loc_series.loc[non_match_mask]
            
            # Combine remote and non-remote results
            loc_series.loc[remote_mask] = remote_locations
            loc_series.loc[non_remote_mask] = formatted_locations
        
    else:
        # All locations are remote
        loc_series.loc[remote_mask] = remote_locations
    
    return loc_series

def extract_work_settings(texts: pd.Series) -> pd.Series:
    """
    Vectorized extraction of work setting from text series.
    
    Args:
        texts: Series of text strings to extract from
        
    Returns:
        Series with extracted work settings
    """
    if texts.isna().all():
        return pd.Series(index=texts.index, dtype='object')
    
    # Convert to strings and search for keywords
    texts = texts.fillna('').astype(str)
    
    # Vectorized pattern matching
    remote_mask = texts.str.contains('remote', case=False)
    hybrid_mask = texts.str.contains('hybrid', case=False)
    
    # Create result series
    result = pd.Series(index=texts.index, dtype='object')
    result.loc[remote_mask] = 'remote'
    result.loc[hybrid_mask & ~remote_mask] = 'hybrid'
    
    return result

def clean_work_settings(df: pd.DataFrame, work_setting_column: str = 'work_setting', 
                      location_column: str = 'location') -> pd.DataFrame:
    """
    Vectorized cleaning of work setting data.
    
    Args:
        df: DataFrame with work setting data
        work_setting_column: Name of work setting column
        location_column: Name of location column
        
    Returns:
        DataFrame with cleaned work settings
    """
    df = df.copy()
    
    # Initialize work_setting column if not present
    if work_setting_column not in df.columns:
        df[work_setting_column] = None
    
    # Extract work settings from location when missing
    if location_column in df.columns:
        mask = df[work_setting_column].isna() | (df[work_setting_column] == '')
        loc_mask = mask & df[location_column].notna()
        
        if loc_mask.any():
            extracted_settings = extract_work_settings(df.loc[loc_mask, location_column])
            update_mask = extracted_settings.notna()
            if update_mask.any():
                df.loc[extracted_settings.index[update_mask], work_setting_column] = extracted_settings[update_mask]
    
    # Standardize work setting values using vectorized operations
    ws_col = df[work_setting_column].fillna('').astype(str)
    
    # Apply standard values based on string content
    remote_mask = ws_col.str.contains('remote', case=False)
    hybrid_mask = ws_col.str.contains('hybrid', case=False)
    df.loc[remote_mask, work_setting_column] = 'remote'
    df.loc[hybrid_mask & ~remote_mask, work_setting_column] = 'hybrid'
    
    # Check for remote mentions in location
    if location_column in df.columns:
        remote_in_location = df[location_column].fillna('').astype(str).str.contains('remote', case=False)
        df.loc[remote_in_location, work_setting_column] = 'remote'
    
    # Set remaining and missing values as in-person
    not_remote_hybrid = ~df[work_setting_column].isin(['remote', 'hybrid'])
    has_value = df[work_setting_column].notna() & (df[work_setting_column] != '')
    df.loc[not_remote_hybrid & has_value, work_setting_column] = 'in-person'
    df[work_setting_column] = df[work_setting_column].fillna('in-person')
    
    return df 