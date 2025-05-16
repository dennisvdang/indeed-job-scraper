#!/usr/bin/env python3
"""SQLAlchemy implementation of job listing repository."""

import logging
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple, cast
import pandas as pd
from sqlalchemy import select, func, update, delete, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...database.connection import get_db_session, db_manager
from ...database.job_schema import JobListing as DBJobListing
from ...database.job_schema import JobDescription as DBJobDescription
from ..models import JobListing
from .base import JobListingRepositoryInterface

logger = logging.getLogger(__name__)


class DBJobListingRepository(JobListingRepositoryInterface):
    """Database repository for job listings using SQLAlchemy."""
    
    def __init__(self, session_factory=None):
        """
        Initialize repository with a session factory.
        
        Args:
            session_factory: Callable that returns a SQLAlchemy session
        """
        self._session_factory = session_factory or get_db_session
        
    def _get_session(self) -> Session:
        """Get a database session."""
        return self._session_factory()
        
    def _model_to_db_entity(self, job_listing: JobListing) -> Tuple[DBJobListing, Optional[DBJobDescription]]:
        """
        Convert Pydantic model to SQLAlchemy entity.
        
        Args:
            job_listing: Pydantic JobListing model
            
        Returns:
            Tuple of (DBJobListing, DBJobDescription) entities
        """
        # Extract description for separate table
        description = job_listing.description
        job_listing_dict = job_listing.to_dict()
        
        # Remove description from dict going to job_listings table
        if 'description' in job_listing_dict:
            del job_listing_dict['description']
            
        # Convert to SQLAlchemy model
        db_job = DBJobListing(**job_listing_dict)
        
        # Create description entity if present
        db_description = None
        if description and job_listing.job_id:
            db_description = DBJobDescription(
                job_id=job_listing.job_id,
                description=description
            )
            
        return db_job, db_description
    
    def _db_entity_to_model(self, db_job: DBJobListing, db_description: Optional[DBJobDescription] = None) -> JobListing:
        """
        Convert SQLAlchemy entity to Pydantic model.
        
        Args:
            db_job: SQLAlchemy JobListing entity
            db_description: SQLAlchemy JobDescription entity
            
        Returns:
            Pydantic JobListing model
        """
        job_dict = {c.name: getattr(db_job, c.name) for c in db_job.__table__.columns}
        
        # Add description if available
        if db_description:
            job_dict['description'] = db_description.description
            
        return JobListing(**job_dict)
    
    def save_job_listing(self, job_listing: JobListing) -> JobListing:
        """
        Save a single job listing to database.
        
        Args:
            job_listing: JobListing to save
            
        Returns:
            The saved JobListing
        """
        session = self._get_session()
        try:
            db_job, db_description = self._model_to_db_entity(job_listing)
            
            # Check if job already exists
            existing = session.query(DBJobListing).filter_by(job_id=db_job.job_id).first()
            if existing:
                logger.debug(f"Job {db_job.job_id} already exists, updating")
                # Update existing record with new data
                for key, value in job_listing.to_dict().items():
                    if key != 'job_id' and hasattr(existing, key):
                        setattr(existing, key, value)
                session.add(existing)
                db_job = existing
            else:
                logger.debug(f"Adding new job {db_job.job_id}")
                session.add(db_job)
            
            # Handle description separately
            if db_description:
                existing_desc = session.query(DBJobDescription).filter_by(job_id=db_description.job_id).first()
                if existing_desc:
                    existing_desc.description = db_description.description
                    session.add(existing_desc)
                else:
                    session.add(db_description)
            
            session.commit()
            
            # Refresh the model with data from DB
            result = self.get_job_listing(db_job.job_id) if db_job.job_id else job_listing
            return result or job_listing
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error saving job listing: {e}")
            raise
        finally:
            session.close()
    
    def save_job_listings(self, job_listings: List[JobListing]) -> int:
        """
        Save multiple job listings to database.
        
        Args:
            job_listings: List of JobListing objects to save
            
        Returns:
            Number of new listings saved
        """
        if not job_listings:
            return 0
            
        # Get existing job IDs
        job_ids = [j.job_id for j in job_listings if j.job_id]
        existing_ids = self.check_job_ids_exist(job_ids)
        
        session = self._get_session()
        new_count = 0
        try:
            # Process in batches for efficiency
            batch_size = 100
            for i in range(0, len(job_listings), batch_size):
                batch = job_listings[i:i + batch_size]
                
                for job in batch:
                    if not job.job_id or job.job_id not in existing_ids:
                        new_count += 1
                    
                    db_job, db_description = self._model_to_db_entity(job)
                    
                    # Handle main job record
                    if db_job.job_id in existing_ids:
                        # Update existing record
                        stmt = (
                            update(DBJobListing)
                            .where(DBJobListing.job_id == db_job.job_id)
                            .values(**{k: v for k, v in db_job.__dict__.items() 
                                    if k != '_sa_instance_state' and k != 'job_id'})
                        )
                        session.execute(stmt)
                    else:
                        # Insert new record
                        session.add(db_job)
                    
                    # Handle description separately
                    if db_description:
                        existing_desc = session.query(DBJobDescription).filter_by(job_id=db_description.job_id).first()
                        if existing_desc:
                            existing_desc.description = db_description.description
                            session.add(existing_desc)
                        else:
                            session.add(db_description)
                
                # Commit batch
                session.commit()
                logger.debug(f"Committed batch of {len(batch)} jobs")
                
            return new_count
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error saving job listings: {e}")
            raise
        finally:
            session.close()
    
    def get_job_listing(self, job_id: str) -> Optional[JobListing]:
        """
        Get a job listing by ID.
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            JobListing if found, None otherwise
        """
        session = self._get_session()
        try:
            # Get job listing
            db_job = session.query(DBJobListing).filter_by(job_id=job_id).first()
            if not db_job:
                return None
                
            # Get description if available
            db_description = session.query(DBJobDescription).filter_by(job_id=job_id).first()
            
            # Convert to model
            return self._db_entity_to_model(db_job, db_description)
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting job listing: {e}")
            return None
        finally:
            session.close()
    
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
        session = self._get_session()
        try:
            # Build query
            query = session.query(DBJobListing)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(DBJobListing, field):
                        if isinstance(value, list):
                            query = query.filter(getattr(DBJobListing, field).in_(value))
                        else:
                            query = query.filter(getattr(DBJobListing, field) == value)
            
            # Apply sorting
            if order_by and hasattr(DBJobListing, order_by):
                order_col = getattr(DBJobListing, order_by)
                query = query.order_by(order_col.desc() if descending else order_col)
            else:
                # Default sort by date_scraped
                query = query.order_by(DBJobListing.date_scraped.desc())
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            # Execute query
            db_jobs = query.all()
            
            # Get descriptions for these jobs
            job_ids = [job.job_id for job in db_jobs if job.job_id]
            descriptions = {}
            if job_ids:
                desc_rows = (
                    session.query(DBJobDescription)
                    .filter(DBJobDescription.job_id.in_(job_ids))
                    .all()
                )
                descriptions = {desc.job_id: desc for desc in desc_rows}
            
            # Convert to models
            return [
                self._db_entity_to_model(
                    db_job, 
                    descriptions.get(db_job.job_id) if db_job.job_id else None
                )
                for db_job in db_jobs
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting job listings: {e}")
            return []
        finally:
            session.close()
    
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
        offset = 0
        while True:
            batch = self.get_job_listings(
                offset=offset,
                limit=batch_size,
                filters=filters
            )
            
            if not batch:
                break
                
            for job in batch:
                yield job
                
            offset += batch_size
            
            if len(batch) < batch_size:
                break
    
    def count_job_listings(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count job listings matching filters.
        
        Args:
            filters: Dictionary of field:value pairs to filter by
            
        Returns:
            Count of matching job listings
        """
        session = self._get_session()
        try:
            # Build query
            query = session.query(func.count(DBJobListing.job_id))
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(DBJobListing, field):
                        if isinstance(value, list):
                            query = query.filter(getattr(DBJobListing, field).in_(value))
                        else:
                            query = query.filter(getattr(DBJobListing, field) == value)
            
            # Execute query
            return query.scalar() or 0
            
        except SQLAlchemyError as e:
            logger.error(f"Error counting job listings: {e}")
            return 0
        finally:
            session.close()
    
    def delete_job_listing(self, job_id: str) -> bool:
        """
        Delete a job listing.
        
        Args:
            job_id: ID of job listing to delete
            
        Returns:
            True if deleted, False if not found
        """
        session = self._get_session()
        try:
            # Delete description first (maintain referential integrity)
            desc_deleted = session.query(DBJobDescription).filter_by(job_id=job_id).delete()
            
            # Delete job listing
            job_deleted = session.query(DBJobListing).filter_by(job_id=job_id).delete()
            
            session.commit()
            return job_deleted > 0
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error deleting job listing: {e}")
            return False
        finally:
            session.close()
    
    def get_unique_values(self, field_name: str) -> List[Any]:
        """
        Get unique values for a specific field.
        
        Args:
            field_name: Field name to get unique values for
            
        Returns:
            List of unique values
        """
        session = self._get_session()
        try:
            if not hasattr(DBJobListing, field_name):
                logger.warning(f"Field {field_name} does not exist in JobListing model")
                return []
                
            query = select(getattr(DBJobListing, field_name)).distinct()
            result = session.execute(query).scalars().all()
            
            # Filter out None values and return as list
            return [value for value in result if value is not None]
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting unique values: {e}")
            return []
        finally:
            session.close()
    
    def check_job_ids_exist(self, job_ids: List[str]) -> Set[str]:
        """
        Check which job IDs already exist in database.
        
        Args:
            job_ids: List of job IDs to check
            
        Returns:
            Set of job IDs that already exist
        """
        if not job_ids:
            return set()
            
        session = self._get_session()
        try:
            query = (
                select(DBJobListing.job_id)
                .where(DBJobListing.job_id.in_(job_ids))
            )
            result = session.execute(query).scalars().all()
            return set(result)
            
        except SQLAlchemyError as e:
            logger.error(f"Error checking job IDs: {e}")
            return set()
        finally:
            session.close()
    
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
        session = self._get_session()
        try:
            # Determine columns
            if columns is None:
                columns = [c.name for c in DBJobListing.__table__.columns]
            else:
                # Ensure all columns exist in model
                valid_columns = [c for c in columns if hasattr(DBJobListing, c)]
                if len(valid_columns) != len(columns):
                    invalid = set(columns) - set(valid_columns)
                    logger.warning(f"Ignoring invalid columns: {', '.join(invalid)}")
                columns = valid_columns
            
            # Build base query
            entities = [getattr(DBJobListing, col) for col in columns]
            query = session.query(*entities)
            
            # Add description if requested
            if include_description:
                query = query.outerjoin(
                    DBJobDescription,
                    DBJobListing.job_id == DBJobDescription.job_id
                )
                entities.append(DBJobDescription.description)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(DBJobListing, field):
                        if isinstance(value, list):
                            query = query.filter(getattr(DBJobListing, field).in_(value))
                        else:
                            query = query.filter(getattr(DBJobListing, field) == value)
            
            # Execute query and convert to DataFrame
            result = query.all()
            
            # Build DataFrame
            df = pd.DataFrame(result, columns=columns + (['description'] if include_description else []))
            
            return df
            
        except (SQLAlchemyError, pd.errors.EmptyDataError) as e:
            logger.error(f"Error getting job listings dataframe: {e}")
            # Return empty DataFrame with correct columns
            col_list = columns + (['description'] if include_description else [])
            return pd.DataFrame(columns=col_list)
        finally:
            session.close()
    
    def update_job_listing(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update fields for a job listing.
        
        Args:
            job_id: ID of job listing to update
            updates: Dictionary of field:value pairs to update
            
        Returns:
            True if updated, False if not found
        """
        if 'job_id' in updates:
            del updates['job_id']  # Prevent updating the ID
            
        session = self._get_session()
        try:
            # Handle description separately if present
            description = None
            if 'description' in updates:
                description = updates.pop('description')
            
            # Update job listing
            stmt = (
                update(DBJobListing)
                .where(DBJobListing.job_id == job_id)
                .values(**updates)
            )
            result = session.execute(stmt)
            updated = result.rowcount > 0
            
            # Update description if needed
            if description is not None and updated:
                desc = session.query(DBJobDescription).filter_by(job_id=job_id).first()
                if desc:
                    desc.description = description
                    session.add(desc)
                else:
                    session.add(DBJobDescription(job_id=job_id, description=description))
            
            session.commit()
            return updated
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error updating job listing: {e}")
            return False
        finally:
            session.close() 