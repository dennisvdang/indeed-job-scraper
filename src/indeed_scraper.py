#!/usr/bin/env python3
"""
Indeed Job Scraper

A tool for scraping job listings from Indeed.com with support for filtering by location,
work arrangement, job type, and other criteria. Results are saved to CSV for further analysis.

Usage:
    python indeed_scraper.py --job-title "Software Engineer" --location "San Francisco" --remote remote --job-type "full-time" --include-descriptions

Author: Dennis
"""

import argparse
import os
import re
import sys
import time
import random
import signal
import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Union
from urllib.parse import quote_plus

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
try:
    # Try relative import (works when installed as a package)
    from .description_scraper import (
        scrape_job_description,
        batch_scrape_descriptions,
        clean_html_description
    )
except ImportError:
    # Fallback to direct import (works when run directly)
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
# Constants
# =====================
REMOTE_WORK_FILTERS = {
    "remote": "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11",
    "hybrid": "&sc=0kf%3Aattr(DSQF7)%3B",
    "onsite": ""  # No specific filter for onsite/in-person
}

JOB_TYPE_FILTERS = {
    "full-time": "&sc=0kf%3Aattr(CF3CP)%3B", 
    "part-time": "&sc=0kf%3Aattr(75GKK)%3B",
    "contract": "&sc=0kf%3Aattr(NJXCK)%3B",
    "temporary": "&sc=0kf%3Aattr(4HKF7)%3B",
    "temp-to-hire": "&sc=0kf%3Aattr(7SBAT)%3B"
}

# Valid options for days ago filter
VALID_DAYS_AGO = [1, 3, 7, 14]

# Selectors for different elements
NEXT_PAGE_SELECTOR = "a[data-testid='pagination-page-next']"
JOB_CONTAINER_SELECTOR = "div[class*='job']"

# Common selectors for job card elements
JOB_CARD_SELECTORS = [
    "div.tapItem",                      # Mobile/app view
    "div.job_seen_beacon",              # Desktop primary
    "div[class*='job_seen_beacon']",    # Desktop with dynamic classes
    "ul.jobsearch-ResultsList > li",    # Container list items 
    "[data-testid='jobListing']",       # New UI with data attributes
    "div[id^='jobCard']"                # Legacy job cards
]

# Job detail field selectors
JOB_TITLE_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "a.jcs-JobTitle"),
    'backup': (By.CSS_SELECTOR, "h2.jobTitle span[title]")
}

JOB_COMPANY_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "[data-testid='company-name']"),
    'backup': (By.CSS_SELECTOR, "span.companyName")
}

JOB_LINK_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "a.jcs-JobTitle"),
    'backup': (By.CSS_SELECTOR, "h2.jobTitle a")
}

JOB_LOCATION_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "[data-testid='text-location']"),
    'backup': (By.CSS_SELECTOR, "div.companyLocation")
}

JOB_SALARY_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "div[class*='salary-snippet-container']"),
    'backup': (By.CSS_SELECTOR, "div.salary-snippet-container")
}

JOB_TYPE_SELECTORS = {
    'primary': (By.CSS_SELECTOR, "div[data-testid='job-type-info']"),  # Modern view
    'backup': (By.CSS_SELECTOR, "div.metadataContainer span.attribute_snippet")  # Older UI
}

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


def convert_days_ago_arg(days_ago: int) -> int:
    """
    Validate the days-ago argument and return it.
    """
    return days_ago if days_ago in VALID_DAYS_AGO else 7


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
    job_type: Optional[str] = None
    date_scraped: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None
    search_url: Optional[str] = None
    date_posted: Optional[str] = None  # Will only be populated when descriptions are fetched

    def to_dict(self) -> Dict:
        """Convert the job listing to a dictionary."""
        # Only include non-None fields to avoid empty columns in CSV
        return {k: v for k, v in self.__dict__.items() if v is not None}


# =====================
# Filesystem Utilities
# =====================
def ensure_data_dirs() -> None:
    """Create data directories if they don't exist."""
    data_dirs = [Path('data/raw'), Path('data/processed')]
    for dir_path in data_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        gitkeep_file = dir_path / '.gitkeep'
        if not gitkeep_file.exists():
            gitkeep_file.touch()


def get_output_filepath(job_title: str, location: Optional[str] = None) -> Path:
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
    
    return Path('data/raw') / filename


def save_jobs_to_csv(jobs: List[JobListing], output_file: Path) -> None:
    """
    Convert job listings to DataFrame and save to CSV.
    
    Args:
        jobs: List of JobListing objects to save
        output_file: Path to the output CSV file
    """
    if not jobs:
        logger.warning("No jobs to save")
        return
    
    # Create dataframe from job dictionaries and format dates
    df = pd.DataFrame([job.to_dict() for job in jobs])
    if 'date_scraped' in df.columns:
        df['date_scraped'] = df['date_scraped'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    
    # Save to CSV
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
    """
    # Create options with anti-detection settings
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.headless = False
    
    # Try with full options first, fall back to minimal if needed
    try:
        logger.info("Setting up browser...")
        driver = uc.Chrome(options=options, version_main=134)
        driver.maximize_window()
        return driver
    except WebDriverException as e:
        logger.warning(f"Could not initialize browser with full options: {str(e)}")
        
        # Fallback to minimal configuration
        logger.info("Trying with minimal configuration")
        try:
            minimal_options = uc.ChromeOptions()
            minimal_options.headless = False
            driver = uc.Chrome(options=minimal_options, version_main=134)
            driver.maximize_window()
            return driver
        except Exception as e:
            logger.error(f"Browser initialization failed: {str(e)}")
            # Let the caller handle this exception
            raise


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
    
    # Get initial document height
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Scroll down gradually with a single script execution
        driver.execute_script("""
            const totalScrolls = 10;
            const scrollHeight = arguments[0];
            const scrollDelay = Math.floor(Math.random() * 100) + 50;
            
            function smoothScroll(step) {
                if (step >= totalScrolls) return;
                
                const position = Math.ceil((step + 1) * scrollHeight / totalScrolls);
                window.scrollTo(0, position);
                
                setTimeout(() => smoothScroll(step + 1), scrollDelay);
            }
            
            smoothScroll(0);
        """, last_height)
        
        # Wait for scrolling to complete and content to load
        time.sleep(2)
        
        # Check if new content was loaded
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    
    # Scroll back up slightly to mimic human behavior
    driver.execute_script("window.scrollTo(0, arguments[0]);", last_height * 0.9)
    random_delay(0.5, 1.0)
    
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
    
    # Select up to max_movements random elements for mouse interaction
    sample_size = min(max_movements, len(elements))
    elements_to_interact = random.sample(elements, sample_size)
    
    # Move mouse to each selected element with random delays
    action = ActionChains(driver)
    for element in elements_to_interact:
        try:
            action.move_to_element(element).perform()
            logger.debug("Moving mouse to random element")
            random_delay(0.3, 1.0)
        except Exception:
            # Silently continue if element is stale or not interactable
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
        logger.info("Navigating to next page...")
        
        # Wait for next button to be clickable
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, NEXT_PAGE_SELECTOR))
        )
        
        # Smooth scroll to button
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            next_button
        )
        random_delay(0.5, 1.0)
        
        # Hover and click
        ActionChains(driver).move_to_element(next_button).perform()
        random_delay(0.3, 0.7)
        
        # Try standard click, use JavaScript click as fallback
        try:
            next_button.click()
        except Exception as e:
            logger.debug(f"Using JavaScript click - {str(e)}")
            driver.execute_script("arguments[0].click();", next_button)
        
        # Wait for new page content to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, JOB_CONTAINER_SELECTOR))
        )
        
        random_delay(2.0, 4.0)
        return True
        
    except (TimeoutException, NoSuchElementException, ElementNotInteractableException) as e:
        logger.warning(f"Could not navigate to next page: {str(e)}")
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
    # Build base URL with properly encoded parameters
    base_url = f"https://www.indeed.com/jobs?q={quote_plus(job_title)}"
    
    # Add location and radius if provided
    if location:
        base_url += f"&l={quote_plus(location)}"
        radius = search_radius or 25  # Default to 25 miles if location provided
        base_url += f"&radius={radius}"
    
    # Add date filter
    if days_ago in VALID_DAYS_AGO:
        base_url += f"&fromage={days_ago}"
    else:
        base_url += "&fromage=7"  # Default to 7 days
    
    # Add remote work filter
    if remote_filter and remote_filter in REMOTE_WORK_FILTERS:
        base_url += REMOTE_WORK_FILTERS[remote_filter]
    
    # Add job type filter
    if job_type and job_type.lower() in JOB_TYPE_FILTERS:
        base_url += JOB_TYPE_FILTERS[job_type.lower()]
    
    return base_url


def find_job_cards(driver: uc.Chrome) -> List:
    """
    Find job card elements using different selectors.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        List of WebElements representing job cards
    """
    job_cards = []
    
    # Try each selector and keep the one that finds the most job cards
    for selector in JOB_CARD_SELECTORS:
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if len(cards) > len(job_cards):
                job_cards = cards
                logger.debug(f"Found {len(cards)} job cards with selector: {selector}")
        except Exception:
            continue
    
    # If standard selectors fail, try a fallback approach
    if not job_cards:
        logger.warning("Using fallback method to find job cards")
        try:
            # Wait for any job-like elements to appear
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, JOB_CONTAINER_SELECTOR))
            )
            # Look for elements with 'job' in the class name
            job_cards = driver.find_elements(By.CSS_SELECTOR, JOB_CONTAINER_SELECTOR)
            logger.debug(f"Found {len(job_cards)} jobs with fallback selector")
        except TimeoutException:
            logger.error("Could not identify any job elements")
    
    return job_cards


def find_job_field(card: object, selectors: dict) -> Optional[object]:
    """
    Try to find a specific field within a job card using primary selector, fall back to backup if not found.
    
    Args:
        card: WebElement to search within
        selectors: Dictionary with 'primary' and 'backup' selector tuples
        
    Returns:
        The found element or None if not found
    """
    try:
        return card.find_element(*selectors['primary'])
    except NoSuchElementException:
        try:
            return card.find_element(*selectors['backup'])
        except NoSuchElementException:
            return None


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
        # Ensure the job card is attached to DOM 
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "job_seen_beacon"))
        )
        
        job_data = {}
        
        # Required fields mapping
        required_fields = {
            'title': JOB_TITLE_SELECTORS,
            'company': JOB_COMPANY_SELECTORS,
            'link': JOB_LINK_SELECTORS
        }
        
        # Non-required fields mapping
        additional_fields = {
            'location': JOB_LOCATION_SELECTORS,
            'salary': JOB_SALARY_SELECTORS,
            'job_type': JOB_TYPE_SELECTORS
        }
        
        # Extract required fields
        for field, selectors in required_fields.items():
            element = find_job_field(card, selectors)
            
            if not element:
                logger.warning(f"Missing required field: {field}")
                return None
                
            if field == 'link':
                job_data[field] = element.get_attribute('href')
                
                # Extract job ID from URL
                job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_data[field])
                if job_id_match:
                    job_data['job_id'] = job_id_match.group(1)
            else:
                # Some job titles are stored in the 'title' attribute
                if field == 'title' and element.get_attribute('title'):
                    job_data[field] = element.get_attribute('title')
                else:
                    job_data[field] = element.text.strip()
        
        # Skip jobs missing required fields
        if not all(job_data.get(field) for field in required_fields.keys()):
            return None
            
        # Extract additional (non-required) fields
        for field, selectors in additional_fields.items():
            element = find_job_field(card, selectors)
            job_data[field] = element.text.strip() if element else None
        
        logger.info(f"Scraped: {job_data['title']} at {job_data['company']}")
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
    if SHOULD_EXIT:
        return False
    
    logger.info("\nIndeed likely shows a CAPTCHA on first visit")
    logger.info("1. Solve the CAPTCHA if present")
    logger.info("2. Wait for the page to fully load")
    logger.info("3. Press Enter ONLY when you're ready to continue...")
    
    # Wait for user input or interruption
    if wait_for_user_continue() is None:
        return False
    
    # Give additional time for page to load completely
    logger.info("Waiting additional time for page to stabilize...")
    time.sleep(5)
    logger.info("Continuing with search...")
    return True


def process_description_batch(
    driver: uc.Chrome, 
    job_listings: List[JobListing], 
    job_urls_to_scrape: List[str],
    current_page: int
) -> None:
    """
    Process a batch of job descriptions and update the corresponding job listings.
    
    Args:
        driver: Chrome driver instance
        job_listings: List of JobListing objects to update with descriptions
        job_urls_to_scrape: List of job URLs to scrape descriptions from
        current_page: Current page number (for logging)
    """
    if not job_urls_to_scrape:
        return
        
    logger.info(f"Batch scraping descriptions for {len(job_urls_to_scrape)} jobs on page {current_page}")
    descriptions_data = batch_scrape_descriptions(driver, job_urls_to_scrape)
    
    # Add descriptions to job listings
    for listing in job_listings:
        # Skip if no job URL
        if not listing.job_url:
            continue
            
        # Add description if available
        if listing.job_url in descriptions_data:
            listing.description = descriptions_data[listing.job_url]
            
        # Add posted date if available (new format with _posted_date suffix)
        posted_date_key = f"{listing.job_url}_posted_date"
        if posted_date_key in descriptions_data:
            listing.date_posted = descriptions_data[posted_date_key]
            logger.debug(f"Added date_posted: {listing.date_posted} for job: {listing.title}")


def is_duplicate_job(
    job_id: Optional[str], 
    title_company: str,
    job_ids: Set[str], 
    seen_title_company_pairs: Set[str],
    current_page_seen: Optional[Set[str]] = None
) -> bool:
    """
    Check if a job is a duplicate based on ID and title-company pair.
    
    Args:
        job_id: Job ID to check
        title_company: Title-company string to check
        job_ids: Set of already seen job IDs 
        seen_title_company_pairs: Set of already seen title-company pairs
        current_page_seen: Set of title-company pairs seen on the current page
        
    Returns:
        True if job is a duplicate, False otherwise
    """
    # Check if job ID is present and already seen
    if job_id and job_id in job_ids:
        return True
        
    # Check if title-company already seen in overall results
    if title_company in seen_title_company_pairs:
        return True
        
    # Check if title-company already seen on current page
    if current_page_seen and title_company in current_page_seen:
        return True
        
    return False


def process_job_cards(
    job_cards: List, 
    driver: uc.Chrome,
    job_ids: Set[str],
    seen_title_company_pairs: Set[str]
) -> Tuple[List[Dict], Set[str]]:
    """
    Process job cards from a page and extract job data.
    
    Args:
        job_cards: List of WebElements representing job cards
        driver: Chrome driver instance
        job_ids: Set of already seen job IDs
        seen_title_company_pairs: Set of already seen title-company pairs
        
    Returns:
        Tuple of (list of job data dictionaries, set of job IDs seen on this page)
    """
    jobs_on_page = []
    current_page_seen = set()
    
    for card in job_cards:
        if SHOULD_EXIT:
            break
            
        job_data = extract_job_data(card, driver)
        
        if job_data:
            job_id = job_data.get('job_id')
            title_company = f"{job_data['title']}_{job_data['company']}"
            
            # Skip duplicates
            if is_duplicate_job(job_id, title_company, job_ids, seen_title_company_pairs, current_page_seen):
                logger.debug(f"Skipping duplicate job: {job_data['title']} at {job_data['company']}")
                continue
            
            current_page_seen.add(title_company)
            jobs_on_page.append(job_data)
        
        random_delay(0.3, 0.7)
    
    return jobs_on_page, current_page_seen


def create_job_listings(
    jobs_data: List[Dict], 
    job_ids: Set[str], 
    seen_title_company_pairs: Set[str],
    search_url: str,
    include_descriptions: bool
) -> Tuple[List[JobListing], List[str]]:
    """
    Create JobListing objects from job data dictionaries and prepare URLs for description scraping.
    
    Args:
        jobs_data: List of job data dictionaries
        job_ids: Set of job IDs to update with new IDs found
        seen_title_company_pairs: Set of title-company pairs to update with new pairs found
        search_url: The search URL used to find these jobs
        include_descriptions: Whether to include full job descriptions in output
        
    Returns:
        Tuple of (list of JobListing objects, list of URLs to scrape descriptions from)
    """
    job_listings = []
    job_urls_to_scrape = []
    
    for job in jobs_data:
        title_company = f"{job['title']}_{job['company']}"
        job_id = job.get('job_id')
        
        # Skip if already seen in previous pages
        if is_duplicate_job(job_id, title_company, job_ids, seen_title_company_pairs):
            continue
        
        # Update tracking sets
        if job_id:
            job_ids.add(job_id)
        seen_title_company_pairs.add(title_company)
        
        # Create the job listing
        job_listing = JobListing(
            title=job['title'],
            company=job['company'],
            location=job.get('location'),
            salary=job.get('salary'),
            job_url=job.get('link'),
            job_id=job_id,
            job_type=job.get('job_type'),
            search_url=search_url
        )
        
        job_listings.append(job_listing)
        
        # If including descriptions, collect URLs for batch processing
        if include_descriptions and job.get('link'):
            job_urls_to_scrape.append(job.get('link'))
    
    return job_listings, job_urls_to_scrape


def scrape_indeed_jobs(
    driver: uc.Chrome,
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    max_pages: int = 3,
    days_ago: int = 7,
    remote_filter: Optional[str] = None,
    job_type: Optional[str] = None,
    include_descriptions: bool = False
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
        include_descriptions: Whether to include full job descriptions in output
        
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
        
        # Scrape page by page
        for current_page in range(1, max_pages + 1):
            # Check if we should exit before starting a new page
            if SHOULD_EXIT:
                logger.info("Exiting: User interrupt")
                break
                
            logger.info(f"Scraping page {current_page} of {max_pages}...")
            
            # Scrape the current page
            job_cards = find_job_cards(driver)
            
            # Process jobs found on this page
            jobs_on_page, current_page_seen = process_job_cards(
                job_cards, driver, job_ids, seen_title_company_pairs
            )
            
            # Check if we found any jobs
            if not jobs_on_page:
                logger.info("No job cards found on this page.")
                logger.info("Reached end of results or no matching jobs.")
                break
            
            logger.info(f"Found {len(jobs_on_page)} unique jobs on this page")
            
            # Create job listings and prepare for description scraping
            job_listings, job_urls_to_scrape = create_job_listings(
                jobs_on_page, job_ids, seen_title_company_pairs, search_url, include_descriptions
            )
            
            # Batch scrape descriptions if needed
            if include_descriptions and job_urls_to_scrape:
                process_description_batch(driver, job_listings, job_urls_to_scrape, current_page)
            
            all_jobs.extend(job_listings)
            logger.info(f"Total unique jobs so far: {len(all_jobs)}")
            
            # Check if we should continue to next page
            if SHOULD_EXIT or current_page >= max_pages:
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
        "--days-ago", 
        type=int, 
        choices=VALID_DAYS_AGO,
        default=7,
        help="Filter for jobs posted within this many days"
    )
    
    parser.add_argument(
        "--remote", 
        type=str, 
        choices=list(REMOTE_WORK_FILTERS.keys()),
        default=None,
        help="Filter for remote, onsite, or hybrid jobs"
    )
    
    parser.add_argument(
        "--job-type", 
        type=str, 
        choices=list(JOB_TYPE_FILTERS.keys()),
        default=None,
        help="Filter by job type (default: None, which shows all job types without filtering)"
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
        "--include-descriptions", 
        action="store_true",
        help="Include full job descriptions in the output (slower but provides more details and accurate posting dates)"
    )
    
    return parser.parse_args()


def main():
    """Entry point for the Indeed job scraper."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: handle_exit_signal())
    signal.signal(signal.SIGTERM, lambda sig, frame: handle_exit_signal())
    
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Configure logging verbosity
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        # Create data directories
        ensure_data_dirs()
        
        # Initialize the browser
        driver = setup_browser()

        # Get output filepath
        output_file = Path(args.output) if args.output else get_output_filepath(args.job_title, args.location)
        
        # Convert days-ago argument
        days_ago = convert_days_ago_arg(args.days_ago)
        
        try:
            # Perform the job scraping
            logger.info(f"Starting job search for '{args.job_title}' in {args.location or 'any location'}")
            
            jobs = scrape_indeed_jobs(
                driver=driver,
                job_title=args.job_title,
                location=args.location,
                search_radius=args.search_radius,
                max_pages=args.num_pages,
                days_ago=days_ago,
                remote_filter=args.remote,
                job_type=args.job_type,
                include_descriptions=args.include_descriptions
            )
            
            # Process and save results
            if jobs:
                save_jobs_to_csv(jobs, output_file)
                logger.info(f"Scraping complete! {len(jobs)} jobs saved to {output_file}")
            else:
                logger.info("No jobs were found for the given search criteria.")
                
        finally:
            # Clean up browser resources
            try:
                driver.quit()
            except Exception as e:
                logger.debug(f"Error during driver cleanup: {str(e)}")
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        sys.exit(1)
    
    # Exit gracefully
    if SHOULD_EXIT:
        sys.exit(130)
    
    return 0


if __name__ == "__main__":
    main()