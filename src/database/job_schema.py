"""
SQLAlchemy schema definition for job listings database.

This module defines the database table structures, field constraints,
and validation rules for job listings data. It provides comprehensive
validation to ensure data integrity before storing in SQL Server.
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime
import logging
import re
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, MetaData
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()
metadata = MetaData()

# Maximum length constraints for string fields
MAX_TITLE_LENGTH = 255
MAX_COMPANY_LENGTH = 255
MAX_LOCATION_LENGTH = 255
MAX_URL_LENGTH = 500
MAX_SOURCE_LENGTH = 100
MAX_JOB_TYPE_LENGTH = 100
MAX_WORK_SETTING_LENGTH = 100
MAX_CITY_STATE_LENGTH = 100
MAX_ZIP_LENGTH = 20
MAX_PERIOD_LENGTH = 50
MAX_JOB_ID_LENGTH = 100

# Default values
DEFAULT_SOURCE = "Indeed"

# SQL Server numeric constraints
MAX_FLOAT_VALUE = 9999999.99

class ValidationError(Exception):
    """Raised when job listing data fails validation."""
    pass

class JobListing(Base):
    """
    SQLAlchemy model for job listings.
    
    This table stores job listings data from various sources, primarily Indeed.
    Schema matches the structure of the job_listings table in SQL Server.
    Includes comprehensive validation to ensure data integrity.
    """
    __tablename__ = 'job_listings'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(MAX_JOB_ID_LENGTH), unique=True, nullable=False, index=True, 
                   comment="Unique identifier for the job listing")
    title = Column(String(MAX_TITLE_LENGTH), nullable=False, 
                  comment="Job title")
    company = Column(String(MAX_COMPANY_LENGTH), nullable=False, 
                    comment="Company name")
    location = Column(String(MAX_LOCATION_LENGTH), 
                     comment="Full location string")
    salary_original = Column(String(MAX_TITLE_LENGTH), 
                            comment="Original salary text as scraped")
    salary_min = Column(Float, 
                       comment="Minimum salary value (any period)")
    salary_max = Column(Float, 
                       comment="Maximum salary value (any period)")
    salary_period = Column(String(MAX_PERIOD_LENGTH), 
                          comment="Salary period (hourly, yearly, etc.)")
    job_url = Column(String(MAX_URL_LENGTH), 
                    comment="URL to the job listing")
    source = Column(String(MAX_SOURCE_LENGTH), default=DEFAULT_SOURCE, 
                   comment="Source of the job listing")
    job_type = Column(String(MAX_JOB_TYPE_LENGTH), 
                     comment="Type of job (Full-time, Part-time, etc.)")
    work_setting = Column(String(MAX_WORK_SETTING_LENGTH), 
                         comment="Work setting (Remote, Hybrid, In-person)")
    date_scraped = Column(DateTime, default=datetime.now, 
                         comment="Date and time when the job was scraped")
    search_url = Column(String(MAX_URL_LENGTH), 
                       comment="URL used for the search that found this job")
    date_posted = Column(DateTime, 
                        comment="Date when the job was posted")
    queried_job_title = Column(String(MAX_TITLE_LENGTH), 
                              comment="Job title used in the search query")
    
    # Additional fields from data cleaning
    city = Column(String(MAX_CITY_STATE_LENGTH), 
                 comment="City parsed from location")
    state = Column(String(MAX_CITY_STATE_LENGTH), 
                  comment="State parsed from location")
    zip_code = Column(String(MAX_ZIP_LENGTH), 
                     comment="ZIP code parsed from location")
    salary_min_yearly = Column(Float, 
                              comment="Minimum yearly salary (normalized)")
    salary_max_yearly = Column(Float, 
                              comment="Maximum yearly salary (normalized)")
    salary_midpoint_yearly = Column(Float, 
                                   comment="Midpoint of yearly salary range")
    
    # Timestamp columns from the actual database
    created_at = Column(DateTime, default=datetime.now, 
                       comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, 
                       comment="Record last update timestamp")
    
    @staticmethod
    def _validate_string_field(value: Any, field_name: str, max_length: int) -> Optional[str]:
        """
        Validate and clean a string field.
        
        Args:
            value: Input value to validate
            field_name: Name of the field (for logging)
            max_length: Maximum allowed length
            
        Returns:
            Cleaned string value or None if invalid/empty
        """
        # Handle None case
        if value is None:
            return None
            
        # Convert to string if not already
        if not isinstance(value, str):
            value = str(value)
        
        # Clean the string
        value = value.strip()
        
        # Check if empty
        if value == '':
            return None
            
        # Truncate if too long
        if len(value) > max_length:
            logger.warning(f"Truncating {field_name} from {len(value)} to {max_length} characters")
            value = value[:max_length]
            
        return value
    
    @staticmethod
    def _validate_numeric_field(value: Any, field_name: str) -> Optional[float]:
        """
        Validate and clean a numeric field.
        
        Args:
            value: Input value to validate
            field_name: Name of the field (for logging)
            
        Returns:
            Cleaned float value or None if invalid
        """
        # Handle None case
        if value is None:
            return None
            
        # Try to convert to float
        try:
            # Handle string inputs
            if isinstance(value, str):
                value = value.strip()
                if value == '':
                    return None
                    
                # Remove any non-numeric characters except decimal point
                value = re.sub(r'[^\d.-]', '', value)
                
            # Convert to float
            float_value = float(value)
            
            # Cap at maximum safe value for SQL Server
            if float_value > MAX_FLOAT_VALUE:
                logger.warning(f"Capping {field_name} value from {float_value} to {MAX_FLOAT_VALUE}")
                float_value = MAX_FLOAT_VALUE
                
            # Round to 2 decimal places to avoid precision issues
            float_value = round(float_value, 2)
            
            return float_value
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid numeric value for {field_name}: {value}, error: {e}")
            return None
    
    @staticmethod
    def _validate_date_field(value: Any, field_name: str) -> Optional[datetime]:
        """
        Validate and clean a date field.
        
        Args:
            value: Input value to validate
            field_name: Name of the field (for logging)
            
        Returns:
            Cleaned datetime value or None if invalid
        """
        # Handle None case
        if value is None:
            return None
            
        # If already a datetime, return as is
        if isinstance(value, datetime):
            return value
            
        # Try to parse string date
        if isinstance(value, str):
            value = value.strip()
            if value == '':
                return None
                
            try:
                # Handle ISO format (with or without timezone)
                if 'T' in value or ' ' in value:
                    # Replace Z with timezone info
                    cleaned_value = value.replace('Z', '+00:00')
                    return datetime.fromisoformat(cleaned_value)
                    
                # Handle date-only format (YYYY-MM-DD)
                if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                    return datetime.fromisoformat(value)
                    
                # Handle other formats
                formats = [
                    '%Y-%m-%d',
                    '%m/%d/%Y',
                    '%d-%m-%Y',
                    '%Y/%m/%d',
                    '%b %d, %Y',
                    '%B %d, %Y'
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                        
                logger.warning(f"Could not parse {field_name} date '{value}': not in any known format")
                return None
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse {field_name} date '{value}': {e}")
                return None
                
        logger.warning(f"Invalid date value for {field_name}: {value}")
        return None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], raise_on_error: bool = True) -> 'JobListing':
        """
        Create JobListing instance from dictionary with data validation.
        
        Args:
            data: Dictionary with job listing data
            raise_on_error: If True, raises ValidationError for missing required fields
            
        Returns:
            JobListing instance with validated data from the dictionary
            
        Raises:
            ValidationError: If required fields are missing and raise_on_error is True
        """
        # Create a copy to avoid modifying the original
        validated_data: Dict[str, Any] = {}
        validation_errors: List[str] = []
        
        # Handle string fields with length validation
        string_fields = {
            'job_id': MAX_JOB_ID_LENGTH,
            'title': MAX_TITLE_LENGTH,
            'company': MAX_COMPANY_LENGTH,
            'location': MAX_LOCATION_LENGTH,
            'job_url': MAX_URL_LENGTH,
            'source': MAX_SOURCE_LENGTH,
            'job_type': MAX_JOB_TYPE_LENGTH,
            'work_setting': MAX_WORK_SETTING_LENGTH,
            'queried_job_title': MAX_TITLE_LENGTH,
            'city': MAX_CITY_STATE_LENGTH,
            'state': MAX_CITY_STATE_LENGTH,
            'zip_code': MAX_ZIP_LENGTH,
            'salary_period': MAX_PERIOD_LENGTH,
            'search_url': MAX_URL_LENGTH
        }
        
        # Validate and clean string fields
        for field, max_length in string_fields.items():
            if field in data:
                validated_data[field] = cls._validate_string_field(data[field], field, max_length)
        
        # Handle date fields
        date_fields = ['date_scraped', 'date_posted']
        for field in date_fields:
            if field in data:
                validated_data[field] = cls._validate_date_field(data[field], field)
                # Set default for date_scraped if missing or invalid
                if field == 'date_scraped' and validated_data.get(field) is None:
                    validated_data[field] = datetime.now()
        
        # Handle numeric salary fields
        numeric_fields = [
            'salary_min', 'salary_max', 'salary_min_yearly', 
            'salary_max_yearly', 'salary_midpoint_yearly'
        ]
        for field in numeric_fields:
            if field in data:
                validated_data[field] = cls._validate_numeric_field(data[field], field)
        
        # Special handling for original salary field which maps to salary_original
        if 'salary' in data:
            validated_data['salary_original'] = cls._validate_string_field(
                data['salary'], 'salary_original', MAX_TITLE_LENGTH
            )
        
        # Description field is now handled by JobDescription class, not needed here
        
        # Verify required fields
        required_fields = [('job_id', 'Job ID'), ('title', 'Job title'), ('company', 'Company name')]
        for field, display_name in required_fields:
            if field not in validated_data or validated_data[field] is None:
                error_msg = f"{display_name} is required"
                validation_errors.append(error_msg)
                logger.error(error_msg)
                
        # If validation errors and we should raise
        if validation_errors and raise_on_error:
            raise ValidationError(f"Validation errors: {'; '.join(validation_errors)}")
            
        # Set defaults
        if 'source' not in validated_data or validated_data['source'] is None:
            validated_data['source'] = DEFAULT_SOURCE
        
        # Ensure date fields are present
        if 'date_scraped' not in validated_data or validated_data['date_scraped'] is None:
            validated_data['date_scraped'] = datetime.now()
            
        return cls(**validated_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Returns:
            Dictionary with non-None values from model
        """
        return {column.name: getattr(self, column.name) 
                for column in self.__table__.columns 
                if getattr(self, column.name) is not None}

class JobDescription(Base):
    """
    SQLAlchemy model for job descriptions.
    
    This table stores the full text job descriptions separately from the job listings
    to improve database performance and reduce table size.
    """
    __tablename__ = 'job_descriptions'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(MAX_JOB_ID_LENGTH), unique=True, nullable=False, index=True,
                   comment="Unique identifier for the job listing - matches job_listings.job_id")
    description = Column(Text, nullable=False,
                        comment="Full job description text")
    created_at = Column(DateTime, default=datetime.now, 
                       comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, 
                       comment="Record last update timestamp")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobDescription':
        """
        Create JobDescription instance from dictionary with data validation.
        
        Args:
            data: Dictionary with job_id and description
            
        Returns:
            JobDescription instance
            
        Raises:
            ValidationError: If required fields are missing
        """
        if 'job_id' not in data or not data['job_id']:
            raise ValidationError("Job ID is required for job description")
        
        if 'description' not in data or not data['description']:
            raise ValidationError("Description is required")
        
        return cls(
            job_id=data['job_id'], 
            description=data['description']
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Returns:
            Dictionary with non-None values from model
        """
        return {column.name: getattr(self, column.name) 
                for column in self.__table__.columns 
                if getattr(self, column.name) is not None} 