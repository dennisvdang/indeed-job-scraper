"""Repository for job listings data storage."""

from .base import JobListingRepositoryInterface
from .db_repository import DBJobListingRepository

# Factory function to get appropriate repository based on configuration
def get_repository() -> JobListingRepositoryInterface:
    """Get repository implementation based on configuration."""
    return DBJobListingRepository() 