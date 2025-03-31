"""Tests for the Indeed job scraper."""

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from typing import Generator

from indeed_scraper import (
    setup_selenium_driver,
    construct_search_url,
    random_delay
)

@pytest.fixture
def driver() -> Generator[webdriver.Chrome, None, None]:
    """Fixture for creating and cleaning up a Chrome driver.
    
    Yields:
        webdriver.Chrome: A configured Chrome webdriver instance.
    """
    driver = setup_selenium_driver()
    yield driver
    driver.quit()

def test_construct_search_url() -> None:
    """Test the URL construction for different search parameters."""
    # Test basic URL construction
    url = construct_search_url("Data Scientist")
    assert "jobs?q=Data+Scientist" in url
    assert "indeed.com" in url
    
    # Test with location
    url = construct_search_url("Data Scientist", "New York")
    assert "l=New+York" in url
    
    # Test with remote option
    url = construct_search_url("Data Scientist", remote=True)
    assert "remotejob=" in url

def test_selenium_driver_setup(driver: webdriver.Chrome) -> None:
    """Test that the Selenium driver is properly configured.
    
    Args:
        driver: The Chrome webdriver fixture.
    """
    # Check that the driver is configured with the correct options
    options = driver.options
    assert "--headless" in str(options.arguments)
    assert "--disable-gpu" in str(options.arguments)
    assert any("user-agent" in arg for arg in options.arguments)

def test_random_delay() -> None:
    """Test that random delay function stays within bounds."""
    min_delay = 1.0
    max_delay = 3.0
    
    # Test multiple times to ensure randomness within bounds
    for _ in range(10):
        start_time = pytest.helpers.time.time()
        random_delay(min_delay, max_delay)
        elapsed = pytest.helpers.time.time() - start_time
        assert min_delay <= elapsed <= max_delay + 0.1  # Add small buffer for execution time 