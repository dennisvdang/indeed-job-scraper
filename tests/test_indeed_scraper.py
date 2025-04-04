"""Tests for the Indeed job scraper."""

import os
import pytest
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from src.indeed_scraper import (
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
    handle_captcha_challenge,
    scrape_indeed_jobs,
    clean_html_description,
    scrape_job_description
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
        date_posted="Posted 2 days ago",
        job_type="Full-time"
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


@patch('time.sleep')
@patch('indeed_scraper.wait_for_user_continue', return_value="")
def test_handle_captcha_challenge(mock_user_continue, mock_sleep, mock_driver):
    """Test handling of CAPTCHA challenges."""
    # Test normal execution (user presses Enter)
    result = handle_captcha_challenge(mock_driver)
    assert result is True
    mock_user_continue.assert_called_once()
    assert mock_sleep.called
    
    # Reset mocks
    mock_user_continue.reset_mock()
    mock_sleep.reset_mock()
    
    # Test user interruption
    mock_user_continue.return_value = None
    result = handle_captcha_challenge(mock_driver)
    assert result is False
    mock_user_continue.assert_called_once()


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
    
    # Test with remote option
    url = construct_search_url("Remote Job", remote="remote")
    assert "remotejob=" in url
    
    # Test with hybrid option
    url = construct_search_url("Hybrid Job", remote="hybrid")
    assert "sc=0kf%3Aattr(DSQF7)%3B" in url
    
    # Test with job type
    url = construct_search_url("Software Engineer", job_type="full-time")
    assert "&jt=fulltime" in url
    
    url = construct_search_url("Software Engineer", job_type="part-time")
    assert "&jt=parttime" in url
    
    url = construct_search_url("Software Engineer", job_type="contract")
    assert "&jt=contract" in url


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
            elif "attribute_snippet" in args[1]:
                element.text = "Full-time"
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
@patch('indeed_scraper.find_job_cards')
@patch('indeed_scraper.extract_job_data')
@patch('indeed_scraper.navigate_to_next_page')
@patch('indeed_scraper.setup_browser')
@patch('indeed_scraper.handle_captcha_challenge', return_value=True)
def test_scrape_indeed_jobs(mock_captcha, mock_setup, mock_navigate, mock_extract, 
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
        {"title": "Job 1", "company": "Company 1", "link": "https://indeed.com/job/1", "job_id": "1", "job_type": "Full-time"},
        {"title": "Job 2", "company": "Company 2", "link": "https://indeed.com/job/2", "job_id": "2", "job_type": "Part-time"},
        {"title": "Job 3", "company": "Company 3", "link": "https://indeed.com/job/3", "job_id": "3", "job_type": "Contract"}
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
    assert jobs[0].job_type == "Full-time"
    assert jobs[1].company == "Company 2"
    assert jobs[1].job_type == "Part-time"
    assert jobs[2].job_id == "3"
    assert jobs[2].job_type == "Contract"


def test_clean_html_description():
    """Test the HTML cleaning function for job descriptions."""
    # Test with various HTML elements
    html_content = """
    <div class="job-desc">
        <h3>Job Description</h3>
        <p>We are looking for a <strong>Software Engineer</strong> with the following skills:</p>
        <ul>
            <li>Python programming</li>
            <li>JavaScript &amp; React.js</li>
            <li>Database experience</li>
        </ul>
        <p>Salary range: $80,000 - $120,000</p>
        <br/>
        <div>Please apply now!</div>
    </div>
    """
    
    cleaned_text = clean_html_description(html_content)
    
    # Check that HTML tags are removed but content is preserved
    assert "Job Description" in cleaned_text
    assert "Software Engineer" in cleaned_text
    assert "Python programming" in cleaned_text
    assert "JavaScript & React.js" in cleaned_text
    assert "• Python programming" in cleaned_text  # Check bullet points
    assert "<strong>" not in cleaned_text  # HTML tags should be removed
    assert "<div>" not in cleaned_text  # HTML tags should be removed
    assert "&amp;" not in cleaned_text  # HTML entities should be converted


def test_scrape_job_description():
    """Test the job description scraping functionality."""
    # Create mock objects
    mock_driver = MagicMock()
    mock_wait = MagicMock()
    mock_desc_element = MagicMock()
    
    # Set up mock behavior
    mock_desc_element.get_attribute.return_value = "<p>Test job description</p>"
    mock_driver.find_element.return_value = mock_desc_element
    mock_driver.current_url = "https://indeed.com/search"
    
    # Patch WebDriverWait
    with patch('indeed_scraper.WebDriverWait', return_value=mock_wait):
        with patch('indeed_scraper.EC.presence_of_element_located'):
            # Test successful description scraping
            result = scrape_job_description(mock_driver, "https://indeed.com/job/123")
            
            # Verify driver interactions
            mock_driver.get.assert_any_call("https://indeed.com/job/123")
            mock_driver.get.assert_any_call("https://indeed.com/search")  # Return to original page
            
            # Verify result
            assert result == "Test job description"  # Should be cleaned HTML
            
            # Test with None returned from get_attribute
            mock_desc_element.get_attribute.return_value = None
            result = scrape_job_description(mock_driver, "https://indeed.com/job/456")
            assert result is None 