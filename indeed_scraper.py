#!/usr/bin/env python3
"""
Indeed Job Scraper

A tool for scraping job listings from Indeed.com with support for filtering by location,
work arrangement, and other criteria. Results are saved to CSV for further analysis.

Usage:
    python indeed_scraper.py --job-title "Software Engineer" --location "San Francisco" --work-arrangement remote

Author: Dennis
Version: 1.0.0
"""

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
    date_scraped: datetime = field(default_factory=datetime.now)

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
        # Create .gitkeep to track empty directories
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
    # Clean up job title for filename
    clean_title = job_title.replace(' ', '_').lower()
    
    # Add location to filename if provided
    if location:
        clean_location = location.replace(' ', '_').lower()
        base_name = f"indeed_{clean_title}_{clean_location}"
    else:
        base_name = f"indeed_{clean_title}"
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}.csv"
    
    # Return full path in data/raw directory
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
        
    # Convert to DataFrame for saving
    df = pd.DataFrame([job.to_dict() for job in jobs])
    
    # Format the datetime before saving
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
    
    Raises:
        WebDriverException: If the browser cannot be initialized
    """
    # Create options for undetected-chromedriver
    options = uc.ChromeOptions()
    
    # Configure options
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Explicitly set headless attribute to avoid attribute error
    options.headless = False
    
    try:
        # Create the driver directly with undetected-chromedriver
        logger.info("Setting up undetected-chromedriver...")
        # Specify version to match Chrome installation
        driver = uc.Chrome(options=options, version_main=134)
        
        # Maximize window
        driver.maximize_window()
        return driver
        
    except Exception as e:
        logger.error(f"Error setting up Chrome with options: {str(e)}")
        
        # Try with minimal configuration
        logger.info("Trying with minimal configuration...")
        minimal_options = uc.ChromeOptions()
        minimal_options.headless = False
        driver = uc.Chrome(options=minimal_options, version_main=134)
        
        try:
            driver.maximize_window()
        except Exception:
            logger.warning("Could not maximize window")
            
        return driver


def check_browser_closed(driver: uc.Chrome) -> bool:
    """
    Check if the browser window has been closed.
    
    Args:
        driver: Chrome driver instance to check
        
    Returns:
        True if browser is closed, False otherwise
    """
    try:
        # Try to get the current window handle
        driver.current_window_handle
        return False
    except (WebDriverException, SessionNotCreatedException):
        return True


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
    
    # Get current scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Scroll down with human-like random pauses
    while True:
        # Scroll down in a randomized steps pattern
        for i in range(10):
            scroll_position = i * last_height / 10
            driver.execute_script(f"window.scrollTo(0, {scroll_position});")
            time.sleep(random.uniform(0.1, 0.3))  # Slight pause between steps
        
        # Wait a bit at the bottom
        time.sleep(random.uniform(0.5, 1.5))
        
        # Calculate new scroll height and check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    
    # Scroll back up a bit (seems more human-like)
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
        
    # Select a random subset of elements
    sample_size = min(max_movements, len(elements))
    if sample_size <= 0:
        return
        
    for element in random.sample(elements, sample_size):
        try:
            action = ActionChains(driver)
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
        # Find next page button
        logger.info("Looking for next page button...")
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='pagination-page-next']"))
        )
        
        # Scroll the button into view smoothly
        logger.info("Scrolling to next page button...")
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
            next_button
        )
        time.sleep(random.uniform(0.8, 1.5))
        
        # Move mouse to button before clicking
        action = ActionChains(driver)
        action.move_to_element(next_button).perform()
        time.sleep(random.uniform(0.5, 1.0))
        
        # Try regular click first, then JavaScript click if needed
        logger.info("Clicking next page button...")
        try:
            next_button.click()
            logger.info("Next page button clicked")
        except Exception as e:
            logger.warning(f"Regular click failed, trying JavaScript click: {str(e)}")
            driver.execute_script("arguments[0].click();", next_button)
            logger.info("Next page button clicked via JavaScript")
        
        # Wait for page to load
        logger.info("Waiting for next page to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='job']"))
        )
        logger.info("Next page loaded successfully")
        
        # Add random delay after navigation
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
    work_arrangement: str = "any"
) -> str:
    """
    Build an Indeed search URL with the specified parameters.
    
    Args:
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: The search radius in miles (default: 25 if location provided)
        days_ago: Filter for jobs posted within this many days
        work_arrangement: Work arrangement preference (remote, hybrid, or any)
        
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
        base_url += f"&radius={radius}"
    
    # Add filters
    if days_ago > 0:
        base_url += f"&fromage={days_ago}"
    
    # Add work arrangement filter
    work_arrangement_filters = {
        "remote": "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11",
        "hybrid": "&sc=0kf%3Aattr(DSQF7)%3B"
    }
    if work_arrangement in work_arrangement_filters:
        base_url += work_arrangement_filters[work_arrangement]
    
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
    
    # Try each selector and use the one that finds the most jobs
    for selector in selectors_to_try:
        cards = driver.find_elements(By.CSS_SELECTOR, selector)
        if len(cards) > len(job_cards):
            job_cards = cards
            logger.debug(f"Found {len(cards)} job cards with selector: {selector}")
    
    # If we found no jobs with any selector, try a different approach
    if not job_cards:
        logger.warning("Could not find job cards with standard selectors, trying alternative...")
        try:
            # Wait for any job-like elements
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='job']"))
            )
            # Look for job containers by common patterns in the HTML structure
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
        # First verify the card is attached to DOM
        WebDriverWait(driver, 1).until(EC.visibility_of(card))
        
        job_data = {}
        
        # Only check for required fields first
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
        
        # Optional fields
        optional_fields = {
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
            }
        }
        
        # Check required fields first
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
                    
                    # Extract job ID from the URL if available
                    job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_data[field])
                    if job_id_match:
                        job_data['job_id'] = job_id_match.group(1)
                else:
                    if field == 'title' and element.get_attribute('title'):
                        job_data[field] = element.get_attribute('title')
                    else:
                        job_data[field] = element.text.strip()
        
        # If any required field is missing, return None
        if missing_required or not all(job_data.get(field) for field in required_fields.keys()):
            return None
            
        # Get optional fields
        for field, locators in optional_fields.items():
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
        
        logger.info(f"Scraped: {job_data['title']} at {job_data['company']}")
        return job_data
        
    except Exception as e:
        logger.error(f"Failed to scrape a job card: {str(e)}")
        return None


def scrape_indeed_jobs(
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    max_pages: int = 3,
    days_ago: int = 7,
    work_arrangement: str = "any"
) -> List[JobListing]:
    """
    Main function to scrape Indeed jobs based on search criteria.
    
    Args:
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: The search radius in miles (default: 25 if location provided)
        max_pages: Maximum number of pages to scrape
        days_ago: Filter for jobs posted within this many days
        work_arrangement: Work arrangement preference (remote, hybrid, or any)
        
    Returns:
        List of JobListing objects containing scraped job data
    """
    global SHOULD_EXIT
    driver = None
    
    try:
        # Initialize browser
        driver = setup_browser()
        
        # Construct and navigate to search URL
        search_url = construct_search_url(
            job_title, location, search_radius, days_ago, work_arrangement
        )
        logger.info(f"Opening search URL: {search_url}")
        driver.get(search_url)
        random_delay(2.0, 4.0)
        
        # Mandatory pause for CAPTCHA solving
        logger.info("\nIndeed likely shows a CAPTCHA on first visit")
        logger.info("1. Solve the CAPTCHA if present")
        logger.info("2. Wait for the page to fully load")
        logger.info("3. Press Enter ONLY when you're ready to continue...")
        
        # Use wait_for_user_continue to handle Ctrl+C
        if SHOULD_EXIT or wait_for_user_continue() is None:
            logger.info("Operation interrupted by user")
            return []
            
        logger.info("Waiting additional time for page to stabilize...")
        time.sleep(5)
        logger.info("Continuing with search...")
        
        # Setup for job collection
        all_jobs: List[JobListing] = []
        job_ids: Set[str] = set()
        seen_title_company_pairs: Set[str] = set()
        
        # Single function to check if we should exit
        def should_stop():
            """Check if we should stop scraping."""
            return SHOULD_EXIT or (driver and check_browser_closed(driver))
        
        # Scrape page by page
        for current_page in range(1, max_pages + 1):
            # Check if we should exit before starting a new page
            if should_stop():
                logger.info("Exiting: User interrupt or browser closed")
                break
                
            logger.info(f"Scraping page {current_page} of {max_pages}...")
            
            # Scroll page naturally to load all content
            scroll_page_naturally(driver)
            
            # Find job cards
            job_cards = find_job_elements(driver)
            logger.info(f"Found {len(job_cards)} job cards on the page")
            
            # Add some random mouse movements
            add_random_mouse_movements(driver, job_cards)
            
            # Process jobs on this page
            jobs_on_page = []
            jobs_already_seen_this_page = set()
            
            # Process each job card
            for card in job_cards:
                # Extract job data
                if should_stop():
                    break
                    
                job_data = extract_job_data(card, driver)
                
                # Process if extraction succeeded
                if job_data:
                    # Create a unique identifier for the job
                    job_id = job_data.get('job_id')
                    title_company = f"{job_data['title']}_{job_data['company']}"
                    
                    # Skip duplicates
                    if ((job_id and job_id in job_ids) or 
                        (title_company in seen_title_company_pairs) or 
                        (title_company in jobs_already_seen_this_page)):
                        logger.debug(f"Skipping duplicate job: {job_data['title']} at {job_data['company']}")
                        continue
                    
                    # Track jobs seen on this page
                    jobs_already_seen_this_page.add(title_company)
                    jobs_on_page.append(job_data)
                
                # Add delay between processing cards
                time.sleep(random.uniform(0.3, 0.7))
              
            # Check if we found any jobs
            if not jobs_on_page:
                logger.info("No job cards found on this page.")
                logger.info("Reached end of results or no matching jobs.")
                break
            
            logger.info(f"Found {len(jobs_on_page)} unique jobs on this page")
            
            # Convert to JobListing objects and add to collection
            for job in jobs_on_page:
                # Create unique identifier
                title_company = f"{job['title']}_{job['company']}"
                
                # Skip if already seen
                if ((job.get('job_id') and job['job_id'] in job_ids) or 
                    (title_company in seen_title_company_pairs)):
                    continue
                
                # Track this job
                if job.get('job_id'):
                    job_ids.add(job['job_id'])
                seen_title_company_pairs.add(title_company)
                
                # Create JobListing object
                job_listing = JobListing(
                    title=job['title'],
                    company=job['company'],
                    location=job.get('location'),
                    salary=job.get('salary'),
                    job_url=job.get('link'),
                    job_id=job.get('job_id'),
                    date_posted=job.get('date_posted')
                )
                
                all_jobs.append(job_listing)
            
            logger.info(f"Total unique jobs so far: {len(all_jobs)}")
            
            # Check if we should stop before attempting navigation
            if should_stop() or current_page >= max_pages:
                break
                
            # Try to navigate to next page
            if not navigate_to_next_page(driver):
                logger.info("Could not navigate to next page. Stopping.")
                break
                
            # Add delay between pages
            random_delay(3.0, 6.0)
        
        logger.info(f"Completed scraping {len(all_jobs)} unique jobs in total")
        return all_jobs
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return []
        
    finally:
        # Clean up browser resources
        if driver and not SHOULD_EXIT:
            try:
                logger.info("Closing browser...")
                driver.quit()
                logger.info("Browser resources released.")
            except Exception:
                pass
            
            # Prevent __del__ from being called during program exit
            driver = None


# =====================
# Command-line Interface
# =====================
def parse_arguments():
    """Parse command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scrape jobs from Indeed.com',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--job-title', 
        type=str, 
        required=True, 
        help='Job title to search for'
    )
    
    parser.add_argument(
        '--location', 
        type=str, 
        default=None, 
        help='Location to search in'
    )
    
    parser.add_argument(
        '--search-radius', 
        type=int, 
        default=None, 
        help='Search radius in miles (default: 25 if location provided)'
    )
    
    parser.add_argument(
        '--max-pages', 
        type=int, 
        default=3, 
        help='Maximum number of pages to scrape'
    )
    
    parser.add_argument(
        '--days-ago', 
        type=int, 
        default=7, 
        help='Filter for jobs posted within this many days'
    )
    
    parser.add_argument(
        '--work-arrangement', 
        type=str, 
        choices=['remote', 'hybrid', 'any'], 
        default='any', 
        help='Work arrangement preference'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='Run without saving output file (useful for testing)'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true', 
        help='Enable debug logging'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the script."""
    # Register signal handler for graceful exit
    signal.signal(signal.SIGINT, lambda signum, frame: handle_exit_signal())
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create data directories
    ensure_data_dirs()
    
    try:
        # Scrape jobs
        jobs = scrape_indeed_jobs(
            job_title=args.job_title,
            location=args.location,
            search_radius=args.search_radius,
            max_pages=args.max_pages,
            days_ago=args.days_ago,
            work_arrangement=args.work_arrangement
        )
        
        # Process results
        if args.dry_run:
            logger.info(f"[DRY RUN] Found {len(jobs)} jobs, no file saved.")
        else:
            # Generate output filepath
            output_file = get_output_filepath(args.job_title, args.location)
            
            # Save the data
            if jobs:
                save_jobs_to_csv(jobs, output_file)
            else:
                logger.info("No jobs were scraped. No file was saved.")
                
        # Exit cleanly
        sys.exit(0)
        
    except KeyboardInterrupt:
        logger.info("Script terminated by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()