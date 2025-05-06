#!/usr/bin/env python3
"""Data cleaning utilities for job listings."""

import re
import numpy as np
import pandas as pd
from typing import Optional

# Pre-compile regular expressions for better performance
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
WHITESPACE_PATTERN = re.compile(r'\s+')

def clean_descriptions(descriptions: pd.Series) -> pd.Series:
    """
    Vectorized cleaning of HTML in job descriptions.
    
    Args:
        descriptions: Series of HTML job descriptions
        
    Returns:
        Series of cleaned plain text descriptions
    """
    if descriptions.isna().all():
        return descriptions
    
    # Handle NaN values
    filled = descriptions.fillna('').astype(str)
    
    # Remove HTML tags
    cleaned = filled.str.replace(HTML_TAG_PATTERN, ' ', regex=True)
    
    # Normalize whitespace
    cleaned = cleaned.str.replace(WHITESPACE_PATTERN, ' ', regex=True).str.strip()
    
    # Preserve original NaN values
    cleaned[descriptions.isna()] = np.nan
    
    return cleaned

def clean_string_field(series: pd.Series) -> pd.Series:
    """
    General string field cleaning.
    
    Args:
        series: Series of string values to clean
        
    Returns:
        Cleaned series
    """
    if series.isna().all():
        return series
    
    # Convert to string, trim whitespace
    result = series.fillna('').astype(str).str.strip()
    
    # Normalize whitespace
    result = result.str.replace(WHITESPACE_PATTERN, ' ', regex=True)
    
    # Restore NaNs
    result[result == ''] = np.nan
    result[series.isna()] = np.nan
    
    return result

def clean_html_description(html_content: str) -> str:
    """
    Convert HTML job description to clean readable text.
    
    Args:
        html_content: HTML content to clean
        
    Returns:
        Clean text description
    """
    if not html_content:
        return ""
    
    # Remove HTML tags
    text = re.sub(HTML_TAG_PATTERN, ' ', html_content)
    
    # Normalize whitespace
    text = re.sub(WHITESPACE_PATTERN, ' ', text).strip()
    
    return text 