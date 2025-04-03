#!/usr/bin/env python3
"""
Indeed Job Scraper

A tool for scraping job listings from Indeed.com with support for filtering by location,
work arrangement, job type, and other criteria. Results are saved to CSV for further analysis.

Usage:
    python indeed_scraper.py --job-title "Software Engineer" --location "San Francisco" --remote remote --job-type "full-time" --fetch-descriptions

Author: Dennis
"""

import os
import re
import sys
import time
import random
import signal
import logging
import csv
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Union

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    SessionNotCreatedException,
    ElementNotInteractableException,
)

# Import functions from description_scraper module
from description_scraper import (
    scrape_job_description,
    batch_scrape_descriptions,
    clean_html_description
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("indeed_scraper")

# Global flag for graceful shutdown
SHOULD_EXIT = False


# =====================
# Core Utilities
# =====================
def handle_exit_signal():
    """Handler for exit signals like Ctrl+C."""
    global SHOULD_EXIT
    logger.info("Received exit signal. Cleaning up...")
    SHOULD_EXIT = True


def wait_for_user_continue(prompt: str = "") -> Optional[str]:
    """
    Wait for user input to continue, with graceful exit handling.
    
    Args:
        prompt: Text to display when asking for input
        
    Returns:
        User input string or None if interrupted
    """
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        logger.info("Input interrupted")
        global SHOULD_EXIT
        SHOULD_EXIT = True
        return None


# =====================
# Data Models
# =====================
@dataclass
class JobListing:
    """Data class to store job listing information."""
    title: str
    company: str
    location: Optional[str] = None
    salary: Optional[str] = None
    job_url: Optional[str] = None
    job_id: Optional[str] = None
    source: str = "Indeed"
    date_posted: Optional[str] = None
    job_type: Optional[str] = None
    date_scraped: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert the job listing to a dictionary."""
        return {k: v for k, v in self.__dict__.items()}


# =====================
# Filesystem Utilities
# =====================
def ensure_data_dirs() -> None:
    """Create data directories if they don't exist."""
    data_dirs = ['data/raw', 'data/processed']
    for dir_path in data_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        gitkeep_file = Path(dir_path) / '.gitkeep'
        if not gitkeep_file.exists():
            gitkeep_file.touch()


def get_output_filepath(job_title: str, location: Optional[str] = None) -> str:
    """
    Generate an organized output filepath for the CSV file.
    
    Args:
        job_title: The job title used in the search
        location: The location used in the search (optional)
        
    Returns:
        Full path to the output CSV file
    """
    clean_title = job_title.replace(' ', '_').lower()
    
    if location:
        clean_location = location.replace(' ', '_').lower()
        base_name = f"indeed_{clean_title}_{clean_location}"
    else:
        base_name = f"indeed_{clean_title}"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}.csv"
    
    return os.path.join('data', 'raw', filename)


def save_jobs_to_csv(jobs: List[JobListing], output_file: str) -> None:
    """
    Convert job listings to DataFrame and save to CSV.
    
    Args:
        jobs: List of JobListing objects to save
        output_file: Path to the output CSV file
    """
    if not jobs:
        logger.warning("No jobs to save")
        return
        
    df = pd.DataFrame([job.to_dict() for job in jobs])
    
    if 'date_scraped' in df.columns:
        df['date_scraped'] = df['date_scraped'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    
    df.to_csv(output_file, index=False)
    logger.info(f"Saved {len(jobs)} jobs to {output_file}")


# =====================
# Browser Automation and Interactions
# =====================
def setup_browser() -> uc.Chrome:
    """
    Configure and return an undetected ChromeDriver for better evasion of detection measures.
    
    Returns:
        Configured Chrome driver instance
    
    Raises:
        WebDriverException: If the browser cannot be initialized
    """
    options = uc.ChromeOptions()
    
    # Necessary flags to prevent Chrome detection mechanisms
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--no-sandbox')  # Required in some environments (Docker)
    options.add_argument('--disable-dev-shm-usage')  # Prevents crashes in containerized environments
    options.headless = False  # Headless mode often triggers bot detection
    
    try:
        logger.info("Setting up undetected-chromedriver...")
        # undetected_chromedriver bypasses Cloudflare and other bot detection systems
        # by mimicking a real Chrome browser with a real user profile
        driver = uc.Chrome(options=options, version_main=134)
        driver.maximize_window()
        return driver
        
    except Exception as e:
        logger.error(f"Error setting up Chrome with options: {str(e)}")
        
        # Try with minimal configuration in case custom options caused the failure
        logger.info("Trying with minimal configuration...")
        minimal_options = uc.ChromeOptions()
        minimal_options.headless = False
        driver = uc.Chrome(options=minimal_options, version_main=134)
        
        try:
            driver.maximize_window()
        except Exception:
            logger.warning("Could not maximize window")
            
        return driver


def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """
    Add a random delay between operations to appear more human-like.
    
    Args:
        min_seconds: Minimum wait time in seconds
        max_seconds: Maximum wait time in seconds
    """
    time.sleep(random.uniform(min_seconds, max_seconds))


def scroll_page_naturally(driver: uc.Chrome) -> None:
    """
    Scroll the page in a human-like manner to load all content.
    
    Args:
        driver: Chrome driver instance
    """
    logger.info("Scrolling page naturally...")
    
    # Get initial document height via JavaScript execution
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Scroll gradually with pauses between movements to mimic human behavior
        # Indeed uses lazy loading, so we need to scroll to load all job listings
        for i in range(10):
            scroll_position = i * last_height / 10
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            time.sleep(random.uniform(0.1, 0.3))
        
        # Pause briefly at the bottom as a human would to read content
        time.sleep(random.uniform(0.5, 1.5))
        
        # Check if new content was loaded (page height increased)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            # No new content loaded, we've reached the bottom
            break
        last_height = new_height
    
    # Scroll back up slightly as a human often does after reaching the bottom
    driver.execute_script(f"window.scrollTo(0, {last_height * 0.9});")
    time.sleep(random.uniform(0.5, 1))
    logger.info("Page scrolling complete")


def add_random_mouse_movements(driver: uc.Chrome, elements: List, max_movements: int = 3) -> None:
    """
    Add random mouse movements to elements to mimic human behavior.
    
    Args:
        driver: Chrome driver instance
        elements: List of WebElements to move the mouse to
        max_movements: Maximum number of elements to interact with
    """
    if not elements:
        return
        
    # Select a subset of elements to interact with
    sample_size = min(max_movements, len(elements))
    if sample_size <= 0:
        return
        
    # Moving the mouse randomly helps evade bot detection that looks for
    # suspiciously direct cursor paths or lack of mouse movement
    for element in random.sample(elements, sample_size):
        try:
            action = ActionChains(driver)
            # ActionChains allows simulation of complex user interactions
            action.move_to_element(element).perform()
            logger.info("Moving mouse to random element")
            time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass


def navigate_to_next_page(driver: uc.Chrome) -> bool:
    """
    Navigate to the next page of search results using human-like interaction.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        True if navigation was successful, False otherwise
    """
    try:
        # WebDriverWait actively polls the DOM until the element is clickable
        # or until the timeout is reached - more reliable than immediate access
        logger.info("Looking for next page button...")
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='pagination-page-next']"))
        )
        
        # Smooth scrolling is more human-like than immediate jumps
        logger.info("Scrolling to next page button...")
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            next_button
        )
        time.sleep(random.uniform(0.8, 1.5))
        
        # Hover over button before clicking - bots often click directly
        action = ActionChains(driver)
        action.move_to_element(next_button).perform()
        time.sleep(random.uniform(0.5, 1.0))
        
        # Try standard click first, then JavaScript click as a fallback
        # JavaScript clicks bypass overlay elements that might block standard clicks
        logger.info("Clicking next page button...")
        try:
            next_button.click()
            logger.info("Next page button clicked")
        except Exception as e:
            logger.warning(f"Regular click failed, trying JavaScript click: {str(e)}")
            driver.execute_script("arguments[0].click();", next_button)
            logger.info("Next page button clicked via JavaScript")
        
        # Wait for new page content to load before continuing
        logger.info("Waiting for next page to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='job']"))
        )
        logger.info("Next page loaded successfully")
        
        random_delay(3.0, 5.0)
        return True
        
    except (TimeoutException, NoSuchElementException, ElementNotInteractableException) as e:
        logger.error(f"Could not navigate to next page: {str(e)}")
        return False


# =====================
# Job Scraping Logic
# =====================
def construct_search_url(
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    days_ago: int = 7,
    remote_filter: Optional[str] = None,
    job_type: Optional[str] = None
) -> str:
    """
    Build an Indeed search URL with the specified parameters.
    
    Args:
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: The search radius in miles (default: 25 if location provided)
        days_ago: Filter for jobs posted within this many days
        remote_filter: Remote work options ('onsite', 'remote', or 'hybrid')
        job_type: Type of job (full-time, part-time, contract, etc.)
        
    Returns:
        Constructed search URL
    """
    # URL encode parameters
    job_title_encoded = job_title.replace(' ', '+')
    location_encoded = location.replace(' ', '+') if location else ""
    
    # Build base URL
    base_url = f"https://www.indeed.com/jobs?q={job_title_encoded}"
    
    # Add location and radius if provided
    if location:
        base_url += f"&l={location_encoded}"
        radius = search_radius or 25  # Default to 25 miles if location provided
        # Using Indeed's actual radius parameter format
        base_url += f"&radius={radius}"
    
    # Add filters
    if days_ago > 0:
        base_url += f"&fromage={days_ago}"
    
    # Add remote work filter
    remote_work_filters = {
        "remote": "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11",
        "hybrid": "&sc=0kf%3Aattr(DSQF7)%3B",
        "onsite": ""  # No specific filter for onsite/in-person
    }
    if remote_filter and remote_filter in remote_work_filters:
        base_url += remote_work_filters[remote_filter]
    
    # Add job type filter
    job_type_filters = {
        "full-time": "&jt=fulltime&sc=0kf%3Aattr(CF3CP)%3B", 
        "part-time": "&jt=parttime",
        "contract": "&jt=contract",
        "temporary": "&jt=temporary",
        "internship": "&jt=internship"
    }
    if job_type and job_type.lower() in job_type_filters:
        base_url += job_type_filters[job_type.lower()]
    
    return base_url


def find_job_elements(driver: uc.Chrome) -> List:
    """
    Find job card elements using different selectors.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        List of WebElements representing job cards
    """
    job_cards = []
    
    # Multiple selectors are tried because Indeed frequently changes their DOM structure
    # and different selectors may work better depending on the user's location, device, etc.
    selectors_to_try = [
        # Common mobile/app selectors
        "div.tapItem",
        # Common desktop selectors - more specific to less specific
        "div.job_seen_beacon",
        "div[class*='job_seen_beacon']",
        # Parent containers - for grouping
        "ul.jobsearch-ResultsList > li",
        # Generic fallbacks - less reliable
        "[data-testid='jobListing']",
        "div[id^='jobCard']"
    ]
    
    # Try each selector and keep the one that finds the most job cards
    for selector in selectors_to_try:
        cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if len(cards) > len(job_cards):
            job_cards = cards
            logger.debug(f"Found {len(cards)} job cards with selector: {selector}")
    
    # If standard selectors fail, try a more generic approach
    if not job_cards:
        logger.warning("Could not find job cards with standard selectors, trying alternative...")
        try:
            # Wait for any job-like elements to appear
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='job']"))
            )
            # Look for elements with 'job' in the class name as a last resort
            job_cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='job']")
            logger.debug(f"Found {len(job_cards)} jobs with alternative selector")
        except Exception:
            logger.error("Could not identify any job elements")
    
    return job_cards


def extract_job_data(card: object, driver: uc.Chrome) -> Optional[Dict]:
    """
    Extract information from a single job card.
    
    Args:
        card: WebElement representing a job card
        driver: Chrome driver instance
        
    Returns:
        Dictionary of job data or None if extraction failed
    """
    try:
        # Ensure the job card is attached to DOM before attempting to extract data
        # This prevents stale element reference exceptions
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "job_seen_beacon"))
        )
        
        job_data = {}
        
        # Required fields to extract
        required_fields = {
            'title': {
                'primary': (By.CSS_SELECTOR, "a.jcs-JobTitle"),
                'backup': (By.CSS_SELECTOR, "h2.jobTitle span[title]")
            },
            'company': {
                'primary': (By.CSS_SELECTOR, "[data-testid='company-name']"),
                'backup': (By.CSS_SELECTOR, "span.companyName")
            },
            'link': {
                'primary': (By.CSS_SELECTOR, "a.jcs-JobTitle"),
                'backup': (By.CSS_SELECTOR, "h2.jobTitle a")
            }
        }
        
        # Additional fields (non-required)
        additional_fields = {
            'location': {
                'primary': (By.CSS_SELECTOR, "[data-testid='text-location']"),
                'backup': (By.CSS_SELECTOR, "div.companyLocation")
            },
            'salary': {
                'primary': (By.CSS_SELECTOR, "div[class*='salary-snippet-container']"),
                'backup': (By.CSS_SELECTOR, "div.salary-snippet-container")
            },
            'date_posted': {
                'primary': (By.CSS_SELECTOR, "span.date"),
                'backup': (By.CSS_SELECTOR, "span[class*='date']")
            },
            'job_type': {
                'primary': (By.CSS_SELECTOR, "div[data-testid='job-type-info']"),  # Modern view
                'backup': (By.CSS_SELECTOR, "div.metadataContainer span.attribute_snippet")  # Older UI
            }
        }
        
        # Using primary and backup selectors improves resilience against
        # Indeed's frequent UI changes and A/B tests
        missing_required = False
        for field, locators in required_fields.items():
            try:
                element = card.find_element(*locators['primary'])
            except NoSuchElementException:
                try:
                    element = card.find_element(*locators['backup'])
                except NoSuchElementException:
                    missing_required = True
                    logger.warning(f"Missing required field: {field}")
                    break
                    
            if element:
                if field == 'link':
                    job_data[field] = element.get_attribute('href')
                    
                    # Extract job ID from URL using regex for unique identification
                    job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_data[field])
                    if job_id_match:
                        job_data['job_id'] = job_id_match.group(1)
                else:
                    # Some job titles are stored in the 'title' attribute rather than text
                    if field == 'title' and element.get_attribute('title'):
                        job_data[field] = element.get_attribute('title')
                    else:
                        job_data[field] = element.text.strip()
        
        # Skip jobs missing required fields
        if missing_required or not all(job_data.get(field) for field in required_fields.keys()):
            return None
            
        # Get additional (non-required) fields
        for field, locators in additional_fields.items():
            try:
                element = card.find_element(*locators['primary'])
            except NoSuchElementException:
                try:
                    element = card.find_element(*locators['backup'])
                except NoSuchElementException:
                    job_data[field] = None
                    continue
                    
            if element:
                job_data[field] = element.text.strip()
            else:
                job_data[field] = None
        
        # Clean up job_type field if it exists
        if job_data.get('job_type'):
            # Extract just the job type part (e.g., "Full-time" from "Full-time · Some other info")
            job_type_raw = job_data['job_type'].split('·')[0].strip()
            
            # Normalize common job type variations
            job_type_mapping = {
                'fulltime': 'Full-time',
                'full time': 'Full-time',
                'full-time': 'Full-time',
                'parttime': 'Part-time',
                'part time': 'Part-time',
                'part-time': 'Part-time',
                'contract': 'Contract',
                'contractor': 'Contract',
                'temporary': 'Temporary',
                'temp': 'Temporary',
                'permanent': 'Permanent',
                'perm': 'Permanent',
                'temp to hire': 'Temp-to-hire',
                'temp-to-hire': 'Temp-to-hire',
                'temptohire': 'Temp-to-hire',
                'internship': 'Internship'
            }
            
            # Try to normalize the job type
            job_type_lower = job_type_raw.lower()
            for key, value in job_type_mapping.items():
                if key in job_type_lower:
                    job_data['job_type'] = value
                    break
            else:
                # If no match found, keep the original text but truncate if too long
                if len(job_type_raw) > 30:
                    job_data['job_type'] = job_type_raw[:30] + "..."
                else:
                    job_data['job_type'] = job_type_raw
        
        job_type_info = f" ({job_data['job_type']})" if job_data.get('job_type') else ""
        logger.info(f"Scraped: {job_data['title']} at {job_data['company']}{job_type_info}")
        return job_data
        
    except Exception as e:
        logger.error(f"Failed to scrape a job card: {str(e)}")
        return None


def handle_captcha_challenge(driver: uc.Chrome) -> bool:
    """
    Pause execution to allow the user to solve any CAPTCHA challenges.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        True if the user confirmed CAPTCHA is solved, False if interrupted
    """
    logger.info("\nIndeed likely shows a CAPTCHA on first visit")
    logger.info("1. Solve the CAPTCHA if present")
    logger.info("2. Wait for the page to fully load")
    logger.info("3. Press Enter ONLY when you're ready to continue...")
    
    # Use wait_for_user_continue to handle Ctrl+C
    if SHOULD_EXIT or wait_for_user_continue() is None:
        logger.info("Operation interrupted by user")
        return False
        
    logger.info("Waiting additional time for page to stabilize...")
    time.sleep(5)
    logger.info("Continuing with search...")
    return True


def scrape_indeed_jobs(
    driver: uc.Chrome,
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    max_pages: int = 3,
    days_ago: int = 7,
    remote_filter: Optional[str] = None,
    job_type: Optional[str] = None,
    fetch_descriptions: bool = False
) -> List[JobListing]:
    """
    Main function to scrape Indeed jobs based on search criteria.
    
    Args:
        driver: Chrome driver instance
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: The search radius in miles (default: 25 if location provided)
        max_pages: Maximum number of pages to scrape
        days_ago: Filter for jobs posted within this many days
        remote_filter: Remote work options ('onsite', 'remote', or 'hybrid')
        job_type: Type of job (full-time, part-time, contract, etc.)
        fetch_descriptions: Whether to fetch job descriptions from detail pages
        
    Returns:
        List of JobListing objects containing scraped job data
    """
    global SHOULD_EXIT
    
    try:
        # Construct and navigate to search URL
        search_url = construct_search_url(
            job_title, location, search_radius, days_ago, remote_filter, job_type
        )
        logger.info(f"Opening search URL: {search_url}")
        driver.get(search_url)
        random_delay(2.0, 4.0)
        
        # Handle any CAPTCHA challenges
        if not handle_captcha_challenge(driver):
            return []
        
        # Collection containers
        all_jobs: List[JobListing] = []
        job_ids: Set[str] = set()
        seen_title_company_pairs: Set[str] = set()
        
        # Check if scraping should be stopped
        def should_stop():
            """Check if we should stop scraping."""
            return SHOULD_EXIT
        
        # Scrape page by page
        for current_page in range(1, max_pages + 1):
            # Check if we should exit before starting a new page
            if should_stop():
                logger.info("Exiting: User interrupt")
                break
                
            logger.info(f"Scraping page {current_page} of {max_pages}...")
            
            # Scrape the current page
            job_cards = find_job_elements(driver)
            
            # Process jobs found on this page
            jobs_on_page = []
            jobs_already_seen_this_page = set()
            
            for card in job_cards:
                if should_stop():
                    break
                    
                job_data = extract_job_data(card, driver)
                
                if job_data:
                    job_id = job_data.get('job_id')
                    title_company = f"{job_data['title']}_{job_data['company']}"
                    
                    # Skip if duplicate
                    if ((job_id and job_id in job_ids) or 
                        (title_company in seen_title_company_pairs) or 
                        (title_company in jobs_already_seen_this_page)):
                        logger.debug(f"Skipping duplicate job: {job_data['title']} at {job_data['company']}")
                        continue
                    
                    jobs_already_seen_this_page.add(title_company)
                    jobs_on_page.append(job_data)
                
                time.sleep(random.uniform(0.3, 0.7))
            
            # Check if we found any jobs
            if not jobs_on_page:
                logger.info("No job cards found on this page.")
                logger.info("Reached end of results or no matching jobs.")
                break
            
            logger.info(f"Found {len(jobs_on_page)} unique jobs on this page")
            
            # Prepare job listings
            job_listings = []
            job_urls_to_scrape = []
            
            for job in jobs_on_page:
                title_company = f"{job['title']}_{job['company']}"
                
                # Skip if already seen
                if ((job.get('job_id') and job['job_id'] in job_ids) or 
                    (title_company in seen_title_company_pairs)):
                    continue
                
                if job.get('job_id'):
                    job_ids.add(job['job_id'])
                seen_title_company_pairs.add(title_company)
                
                # Create the job listing
                job_listing = JobListing(
                    title=job['title'],
                    company=job['company'],
                    location=job.get('location'),
                    salary=job.get('salary'),
                    job_url=job.get('link'),
                    job_id=job.get('job_id'),
                    date_posted=job.get('date_posted'),
                    job_type=job.get('job_type')
                )
                
                job_listings.append(job_listing)
                
                # If fetching descriptions, collect URLs for batch processing
                if fetch_descriptions and job.get('link'):
                    job_urls_to_scrape.append(job.get('link'))
            
            # Batch scrape descriptions if needed
            if fetch_descriptions and job_urls_to_scrape:
                logger.info(f"Batch scraping descriptions for {len(job_urls_to_scrape)} jobs on page {current_page}")
                descriptions = batch_scrape_descriptions(driver, job_urls_to_scrape)
                
                # Add descriptions to job listings
                for i, listing in enumerate(job_listings):
                    if listing.job_url in descriptions:
                        listing.description = descriptions[listing.job_url]
            
            all_jobs.extend(job_listings)
            logger.info(f"Total unique jobs so far: {len(all_jobs)}")
            
            # Check if we should continue to next page
            if should_stop() or current_page >= max_pages:
                break
                
            if not navigate_to_next_page(driver):
                logger.info("Could not navigate to next page. Stopping.")
                break
                
            random_delay(3.0, 6.0)
        
        logger.info(f"Completed scraping {len(all_jobs)} unique jobs in total")
        return all_jobs
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []


# =====================
# Command-line Interface
# =====================
def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the scraper.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Scrape job listings from Indeed.com with advanced filtering options",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--job-title", 
        type=str, 
        required=True, 
        help="Job title or search query"
    )
    
    parser.add_argument(
        "--location", 
        type=str, 
        default=None, 
        help="Location for job search (e.g., 'New York, NY' or 'Remote')"
    )
    
    parser.add_argument(
        "--search-radius", 
        type=int, 
        default=25,
        help="Search radius in miles from the specified location"
    )
    
    parser.add_argument(
        "--num-pages", 
        type=int, 
        default=3,
        help="Number of result pages to scrape"
    )
    
    parser.add_argument(
        "--remote", 
        type=str, 
        choices=["onsite", "remote", "hybrid"],
        default=None,
        help="Filter for remote, onsite, or hybrid jobs"
    )
    
    parser.add_argument(
        "--job-type", 
        type=str, 
        choices=["full-time", "part-time", "contract", "temporary", "internship"],
        default=None,
        help="Filter by job type"
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        default=None,
        help="Output CSV file path (default: auto-generated based on search)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--fetch-descriptions", 
        action="store_true",
        help="Fetch detailed job descriptions (makes the scraping process slower but provides full job details)"
    )
    
    args = parser.parse_args()
    
    # Configure logging verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    return args


def main():
    """Entry point for the Indeed job scraper."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: handle_exit_signal())
    signal.signal(signal.SIGTERM, lambda sig, frame: handle_exit_signal())
    
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Create data directories
        ensure_data_dirs()
        
        # Initialize the browser
        driver = setup_browser()

        # Get output filepath
        output_file = args.output
        if not output_file:
            output_file = get_output_filepath(args.job_title, args.location)
        
        try:
            # Do the scraping
            logger.info(f"Starting job search for '{args.job_title}' in {args.location or 'any location'}")
            
            jobs = scrape_indeed_jobs(
                driver=driver,
                job_title=args.job_title,
                location=args.location,
                search_radius=args.search_radius,
                max_pages=args.num_pages,
                remote_filter=args.remote,
                job_type=args.job_type,
                fetch_descriptions=args.fetch_descriptions
            )
            
            # Process results
            if jobs:
                save_jobs_to_csv(jobs, output_file)
                logger.info(f"Scraping complete! {len(jobs)} jobs saved to {output_file}")
            else:
                logger.info("No jobs were found for the given search criteria.")
                
        finally:
            # Clean up browser resources
            try:
                driver.quit()
            except:
                pass
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        sys.exit(1)
    
    # Exit gracefully
    if SHOULD_EXIT:
        sys.exit(130)  # Standard exit code for SIGINT
    
    return 0


if __name__ == "__main__":
    main()