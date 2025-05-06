#!/usr/bin/env python3
"""Data enrichment utilities for job listings."""

import re
import numpy as np
import pandas as pd
from typing import Dict, Optional

# Pre-compile regular expressions for better performance
SALARY_AMOUNT_PATTERN = re.compile(r'\$?([\d,]+\.?\d*)')
HOUR_PATTERN = re.compile(r'hour', re.IGNORECASE)
WEEK_PATTERN = re.compile(r'week', re.IGNORECASE)
MONTH_PATTERN = re.compile(r'month', re.IGNORECASE)

def parse_salaries(salary_texts: pd.Series) -> pd.DataFrame:
    """
    Vectorized parsing of salary text into structured components.
    
    Args:
        salary_texts: Series of salary text strings
        
    Returns:
        DataFrame with parsed salary components
    """
    # Initialize result DataFrame
    result = pd.DataFrame({
        'salary_min': pd.Series(dtype='float'),
        'salary_max': pd.Series(dtype='float'),
        'salary_period': pd.Series(dtype='object'),
        'salary_original': salary_texts
    })
    
    # Skip if all NaN
    if salary_texts.isna().all():
        return result
    
    # Convert to string and extract dollar amounts
    valid_mask = salary_texts.notna() & (salary_texts != '')
    if valid_mask.any():
        texts = salary_texts[valid_mask].astype(str)
        
        # Extract all dollar amounts from each text
        # This is a bit complex as we need multiple matches per text
        def extract_amounts(text):
            matches = SALARY_AMOUNT_PATTERN.findall(text)
            return [float(amt.replace(',', '')) for amt in matches] if matches else []
        
        all_amounts = texts.apply(extract_amounts)
        has_amounts = all_amounts.str.len() > 0
        
        # Determine payment period using vectorized operations
        texts_lower = texts.str.lower()
        hourly_mask = texts_lower.str.contains('hour')
        weekly_mask = texts_lower.str.contains('week')
        monthly_mask = texts_lower.str.contains('month')
        
        result.loc[valid_mask & hourly_mask, 'salary_period'] = 'hourly'
        result.loc[valid_mask & weekly_mask & ~hourly_mask, 'salary_period'] = 'weekly'
        result.loc[valid_mask & monthly_mask & ~hourly_mask & ~weekly_mask, 'salary_period'] = 'monthly'
        result.loc[valid_mask & ~hourly_mask & ~weekly_mask & ~monthly_mask, 'salary_period'] = 'yearly'
        
        # Set min and max values
        for idx in all_amounts[has_amounts].index:
            amounts = all_amounts.loc[idx]
            if len(amounts) >= 2:
                result.loc[idx, 'salary_min'] = min(amounts)
                result.loc[idx, 'salary_max'] = max(amounts)
            elif amounts:
                result.loc[idx, 'salary_min'] = amounts[0]
                result.loc[idx, 'salary_max'] = amounts[0]
    
    return result

def standardize_salaries(parsed_salaries: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized standardization of salary values to yearly amounts.
    
    Args:
        parsed_salaries: DataFrame with parsed salary components
        
    Returns:
        DataFrame with standardized yearly salary values
    """
    result = parsed_salaries.copy()
    
    # Skip if empty
    if result.empty:
        result['salary_min_yearly'] = pd.Series(dtype='float')
        result['salary_max_yearly'] = pd.Series(dtype='float')
        return result
    
    # Define conversion multipliers
    conversions = {
        'hourly': 40 * 50,  # 40 hours/week, 50 weeks/year
        'weekly': 50,       # 50 weeks/year
        'monthly': 12,      # 12 months/year
        'yearly': 1
    }
    
    # Create a multiplier column based on period
    valid_mask = result['salary_min'].notna() & result['salary_period'].notna()
    if valid_mask.any():
        # Map period to multiplier using vectorized operation
        multipliers = result.loc[valid_mask, 'salary_period'].map(conversions)
        
        # Apply multipliers to min and max salaries
        result.loc[valid_mask, 'salary_min_yearly'] = result.loc[valid_mask, 'salary_min'] * multipliers
        
        max_valid = valid_mask & result['salary_max'].notna()
        if max_valid.any():
            result.loc[max_valid, 'salary_max_yearly'] = result.loc[max_valid, 'salary_max'] * multipliers
    
    return result

def calculate_salary_midpoints(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate salary midpoints from min and max yearly values.
    
    Args:
        df: DataFrame with salary min/max yearly values
        
    Returns:
        DataFrame with added midpoint column
    """
    df = df.copy()
    
    # Calculate midpoint using vectorized operations
    min_yearly_mask = df['salary_min_yearly'].notna()
    max_yearly_mask = df['salary_max_yearly'].notna()
    
    # Both min and max available
    both_mask = min_yearly_mask & max_yearly_mask
    if both_mask.any():
        df.loc[both_mask, 'salary_midpoint_yearly'] = (
            df.loc[both_mask, 'salary_min_yearly'] + df.loc[both_mask, 'salary_max_yearly']
        ) / 2
    
    # Only min available
    min_only_mask = min_yearly_mask & ~max_yearly_mask
    if min_only_mask.any():
        df.loc[min_only_mask, 'salary_midpoint_yearly'] = df.loc[min_only_mask, 'salary_min_yearly']
    
    # Only max available
    max_only_mask = ~min_yearly_mask & max_yearly_mask
    if max_only_mask.any():
        df.loc[max_only_mask, 'salary_midpoint_yearly'] = df.loc[max_only_mask, 'salary_max_yearly']
    
    return df

def clean_salary_data(df: pd.DataFrame, salary_column: str = 'salary') -> pd.DataFrame:
    """
    Vectorized extraction and standardization of salary information.
    
    Args:
        df: DataFrame with salary data
        salary_column: Name of salary column
        
    Returns:
        DataFrame with cleaned and standardized salary data
    """
    if salary_column not in df.columns:
        return df
    
    df = df.copy()
    
    # Parse and standardize salaries
    parsed = parse_salaries(df[salary_column])
    standardized = standardize_salaries(parsed)
    
    # Add salary components to main DataFrame
    for col in ['salary_min', 'salary_max', 'salary_period']:
        df[col] = parsed[col]
    
    for col in ['salary_min_yearly', 'salary_max_yearly']:
        df[col] = standardized[col]
    
    # Calculate midpoint
    df = calculate_salary_midpoints(df)
    
    return df 