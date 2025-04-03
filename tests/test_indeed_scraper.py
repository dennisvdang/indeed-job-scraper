"""Tests for the Indeed job scraper."""

import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from indeed_scraper import (
    # Data models
    JobListing,
    # Filesystem
    get_output_filepath,
    save_jobs_to_csv,
    # Browser automation
    setup_browser,
    # Job scraping
    construct_search_url,
    extract_job_data,
    scrape_indeed_jobs
)


@pytest.fixture
def mock_driver():
    """Mock Chrome driver for testing without real browser interaction."""
    mock = MagicMock(spec=uc.Chrome)
    mock.execute_script.return_value = 1000  # Mock scroll height
    mock.find_elements.return_value = []
    return mock


@pytest.fixture
def sample_job_listing():
    """Create a sample JobListing for testing."""
    return JobListing(
        title="Software Engineer",
        company="Test Company",
        location="Remote",
        salary="$100,000 - $150,000 a year",
        job_url="https://indeed.com/job/123",
        job_id="abc123",
        date_posted="Posted 2 days ago"
    )


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing file operations."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "raw").mkdir()
    (data_dir / "processed").mkdir()
    return data_dir


# =====================
# Data Models Tests
# =====================
def test_job_listing_creation(sample_job_listing):
    """Test JobListing creation and default values."""
    # Test required fields
    assert sample_job_listing.title == "Software Engineer"
    assert sample_job_listing.company == "Test Company"
    
    # Test additional fields
    assert sample_job_listing.location == "Remote"
    assert sample_job_listing.salary == "$100,000 - $150,000 a year"
    
    # Test defaults
    assert sample_job_listing.source == "Indeed"
    assert isinstance(sample_job_listing.date_scraped, datetime)


def test_job_listing_to_dict(sample_job_listing):
    """Test conversion of JobListing to dictionary."""
    job_dict = sample_job_listing.to_dict()
    assert isinstance(job_dict, dict)
    assert job_dict["title"] == "Software Engineer"
    assert job_dict["company"] == "Test Company"
    assert job_dict["job_id"] == "abc123"
    assert "date_scraped" in job_dict


# =====================
# Filesystem Utilities Tests
# =====================
def test_get_output_filepath():
    """Test output filepath generation with different inputs."""
    # Test with job title only
    path = get_output_filepath("Software Engineer")
    assert "indeed_software_engineer_" in path
    assert path.endswith(".csv")
    assert "data/raw" in path
    
    # Test with job title and location
    path = get_output_filepath("Data Scientist", "New York")
    assert "indeed_data_scientist_new_york_" in path
    assert path.endswith(".csv")


def test_save_jobs_to_csv(sample_job_listing, tmp_path):
    """Test saving job listings to CSV."""
    # Prepare test data
    test_file = tmp_path / "test_jobs.csv"
    jobs = [sample_job_listing]
    
    # Save to CSV
    save_jobs_to_csv(jobs, str(test_file))
    
    # Verify the file exists and contains correct data
    assert test_file.exists()
    df = pd.read_csv(test_file)
    assert len(df) == 1
    assert df.iloc[0]["title"] == "Software Engineer"
    assert df.iloc[0]["company"] == "Test Company"
    assert "date_scraped" in df.columns


# =====================
# Browser Automation Tests
# =====================
@patch('undetected_chromedriver.Chrome')
def test_setup_browser(mock_chrome):
    """Test browser setup with mock Chrome driver."""
    # Configure mock
    instance = mock_chrome.return_value
    instance.options = MagicMock()
    
    # Call function
    driver = setup_browser()
    
    # Verify Chrome driver was created with expected options
    mock_chrome.assert_called_once()
    assert driver == instance


# =====================
# Job Scraping Tests
# =====================
def test_construct_search_url():
    """Test search URL construction with various parameters."""
    # Test basic URL
    url = construct_search_url("Software Engineer")
    assert "indeed.com/jobs?q=Software+Engineer" in url
    
    # Test with location
    url = construct_search_url("Data Analyst", "New York")
    assert "indeed.com/jobs?q=Data+Analyst" in url
    assert "&l=New+York" in url
    
    # Test with radius
    url = construct_search_url("Developer", "Boston", search_radius=50)
    assert "&radius=50" in url
    
    # Test with days ago
    url = construct_search_url("Manager", days_ago=14)
    assert "&fromage=14" in url
    
    # Test with work arrangement
    url = construct_search_url("Remote Job", work_arrangement="remote")
    assert "remotejob=" in url


@patch('selenium.webdriver.support.ui.WebDriverWait')
def test_extract_job_data(mock_wait, mock_driver):
    """Test job data extraction with mock elements."""
    # Create a mock card and elements
    mock_card = MagicMock()
    
    def mock_find_element(*args):
        """Create different mock elements based on the selector."""
        element = MagicMock()
        if args[0] == By.CSS_SELECTOR:
            if "title" in args[1]:
                element.text = "Test Job Title"
                element.get_attribute.return_value = "Test Job Title"
            elif "company" in args[1]:
                element.text = "Test Company"
            elif "location" in args[1]:
                element.text = "Test Location"
            elif "salary" in args[1]:
                element.text = "$100k - $150k"
            elif "link" in args[1] or args[1].endswith("a"):
                element.get_attribute.return_value = "https://indeed.com/job/test123"
        return element
    
    mock_card.find_element = mock_find_element
    
    # Test extraction
    with patch('selenium.webdriver.support.ui.WebDriverWait.until', return_value=True):
        job_data = extract_job_data(mock_card, mock_driver)
    
    # Verify extracted data
    assert job_data is not None
    assert job_data.get("title") == "Test Job Title"
    assert job_data.get("company") == "Test Company"


@patch('indeed_scraper.scroll_page_naturally')
@patch('indeed_scraper.find_job_elements')
@patch('indeed_scraper.extract_job_data')
@patch('indeed_scraper.navigate_to_next_page')
@patch('indeed_scraper.setup_browser')
@patch('indeed_scraper.wait_for_user_continue', return_value="")
def test_scrape_indeed_jobs(mock_wait, mock_setup, mock_navigate, mock_extract, 
                          mock_find, mock_scroll):
    """Test the main scraping function with mocks."""
    # Configure mocks
    mock_driver = MagicMock()
    mock_setup.return_value = mock_driver
    mock_driver.get.return_value = None
    
    # Set up job card mocks
    mock_cards = [MagicMock() for _ in range(3)]
    mock_find.return_value = mock_cards
    
    # Set up job data mocks
    mock_extract.side_effect = [
        {"title": "Job 1", "company": "Company 1", "link": "https://indeed.com/job/1", "job_id": "1"},
        {"title": "Job 2", "company": "Company 2", "link": "https://indeed.com/job/2", "job_id": "2"},
        {"title": "Job 3", "company": "Company 3", "link": "https://indeed.com/job/3", "job_id": "3"}
    ]
    
    # Navigate mock returns True to simulate successful navigation
    mock_navigate.return_value = True
    
    # Call function with test parameters
    jobs = scrape_indeed_jobs(
        job_title="Test Job",
        location="Test Location",
        max_pages=2
    )
    
    # Verify results
    assert len(jobs) == 3
    assert jobs[0].title == "Job 1"
    assert jobs[1].company == "Company 2"
    assert jobs[2].job_id == "3" 