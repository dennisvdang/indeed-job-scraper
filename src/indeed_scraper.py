#!/usr/bin/env python3
"""
Indeed Job Scraper

A tool for scraping job listings from Indeed.com with support for filtering.
Results are saved to CSV with optional job descriptions.

Usage:
    python indeed_scraper.py --job-title "Software Engineer" --location "San Francisco" --job-type "full-time"

Author: Dennis
"""

import argparse
import logging
import random
import re
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import quote_plus

import pandas as pd
import undetected_chromedriver as uc
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement

# Import helper modules
try:
    from .description_scraper import batch_scrape_descriptions
    from .data_cleaner import clean_dataframe
except ImportError:
    from description_scraper import batch_scrape_descriptions
    from data_cleaner import clean_dataframe

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
WORK_SETTING_FILTERS = {
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

VALID_DAYS_AGO = [1, 3, 7, 14]

# Selectors for job elements
JOB_CARD_SELECTOR = "div.job_seen_beacon, div.tapItem, [data-testid='jobListing']"
NEXT_PAGE_SELECTOR = "a[data-testid='pagination-page-next']"

# Field selectors within job cards
JOB_FIELD_SELECTORS = {
    'title': [(By.CSS_SELECTOR, "a.jcs-JobTitle"), (By.CSS_SELECTOR, "h2.jobTitle span[title]")],
    'company': [(By.CSS_SELECTOR, "[data-testid='company-name']"), (By.CSS_SELECTOR, "span.companyName")],
    'location': [(By.CSS_SELECTOR, "[data-testid='text-location']"), (By.CSS_SELECTOR, "div.companyLocation")],
    'salary': [(By.CSS_SELECTOR, "div[class*='salary-snippet-container']"), (By.CSS_SELECTOR, "div.salary-snippet-container")],
    'job_type': [(By.CSS_SELECTOR, "div[data-testid='job-type-info']"), (By.CSS_SELECTOR, "div.metadataContainer span.attribute_snippet")],
    'work_setting': [(By.CSS_SELECTOR, "div[data-testid='work-setting-info']"), (By.CSS_SELECTOR, "div.metadataContainer span.attribute_snippet[data-work-setting]")],
    'link': [(By.CSS_SELECTOR, "a.jcs-JobTitle"), (By.CSS_SELECTOR, "h2.jobTitle a")]
}

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
    work_setting: Optional[str] = None
    date_scraped: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None
    search_url: Optional[str] = None
    date_posted: Optional[str] = None
    is_ad: bool = False

    def to_dict(self) -> Dict:
        """Convert the job listing to a dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


# =====================
# Utils - Signal Handling
# =====================
def handle_exit_signal(sig=None, frame=None) -> None:
    """Handle exit signals like Ctrl+C."""
    global SHOULD_EXIT
    logger.info("Received exit signal. Cleaning up...")
    SHOULD_EXIT = True


def get_user_input(prompt: str = "") -> Optional[str]:
    """Get user input with graceful exit handling."""
    try:
        return input(prompt)
    except (KeyboardInterrupt, EOFError):
        handle_exit_signal()
        return None


# =====================
# Browser Setup
# =====================
def setup_browser() -> uc.Chrome:
    """Configure and return an undetected ChromeDriver instance."""
    logger.info("Setting up browser...")
    
    # Create options with anti-detection settings
    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.headless = False
    
    try:
        driver = uc.Chrome(options=options)
        driver.maximize_window()
        return driver
    except WebDriverException as e:
        logger.warning(f"Browser initialization with full options failed: {e}")
        
        # Fallback to minimal configuration
        minimal_options = uc.ChromeOptions()
        minimal_options.headless = False
        try:
            driver = uc.Chrome(options=minimal_options)
            driver.maximize_window()
            return driver
        except Exception as e:
            logger.error(f"Browser initialization failed: {e}")
            raise


# =====================
# File Operations
# =====================
def ensure_data_dirs() -> None:
    """Create data directories if they don't exist."""
    for dir_path in [Path('data/raw'), Path('data/processed')]:
        dir_path.mkdir(parents=True, exist_ok=True)


def get_output_filepath(job_title: str, location: Optional[str] = None) -> Path:
    """Generate an output filepath for the CSV file."""
    clean_title = job_title.replace(' ', '').lower()
    
    if location:
        clean_location = location.lower().replace(',', '').replace(' ', '')
        base_name = f"indeed_{clean_title}_{clean_location}"
    else:
        base_name = f"indeed_{clean_title}"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path('data/raw') / f"{base_name}_{timestamp}.csv"


def export_jobs_to_csv(jobs: List[JobListing], output_file: Path) -> None:
    """Create dataframe from job listings and export to CSV file."""
    if not jobs:
        logger.warning("No jobs to save")
        return
    
    # Create dataframe from job dictionaries
    df = pd.DataFrame([job.to_dict() for job in jobs])
    
    # Format datetime fields
    if 'date_scraped' in df.columns:
        df['date_scraped'] = df['date_scraped'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if hasattr(x, 'strftime') else x
        )
    
    # Clean the dataframe
    try:
        logger.info("Cleaning data...")
        df = clean_dataframe(
            df,
            location_column='location',
            work_setting_column='work_setting',
            salary_column='salary',
            description_column='description'
        )
    except Exception as e:
        logger.error(f"Data cleaning error: {e}")
        logger.info("Continuing with original dataframe")
    
    # Save CSV
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    logger.info(f"Saved {len(df)} jobs to {output_file}")


# =====================
# Page Navigation
# =====================
def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Add a random delay to mimic human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def scroll_page(driver: uc.Chrome) -> None:
    """Scroll the page to load all content."""
    logger.info("Scrolling page...")
    
    # Simple scroll implementation
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    # Scroll in chunks
    for i in range(1, 11):
        driver.execute_script(f"window.scrollTo(0, {i * last_height / 10});")
        time.sleep(0.2)
    
    # Wait for content to load
    time.sleep(1)
    
    # Check if more content loaded
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height > last_height:
        # Scroll once more to the bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)


def navigate_to_next_page(driver: uc.Chrome) -> bool:
    """Navigate to the next page of search results."""
    try:
        # Find the next button
        next_buttons = driver.find_elements(By.CSS_SELECTOR, NEXT_PAGE_SELECTOR)
        if not next_buttons:
            logger.info("No next page button found - reached the last page")
            return False
        
        # Get the next page URL and navigate
        next_page_url = next_buttons[0].get_attribute('href')
        if not next_page_url:
            return False
            
        current_url = driver.current_url
        driver.get(next_page_url)
        
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, JOB_CARD_SELECTOR))
        )
        
        # Verify navigation succeeded
        if driver.current_url == current_url:
            return False
            
        random_delay()
        return True
        
    except (TimeoutException, NoSuchElementException, ElementNotInteractableException):
        return False


# =====================
# Job Search & Scraping
# =====================
def get_search_url(
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    days_ago: int = 7,
    work_setting: Optional[str] = None,
    job_type: Optional[str] = None
) -> str:
    """Build an Indeed search URL with the specified parameters."""
    # Base URL with job title
    url = f"https://www.indeed.com/jobs?q={quote_plus(job_title)}"
    
    # Add location and radius if provided
    if location:
        url += f"&l={quote_plus(location)}"
        radius = search_radius or 25
        url += f"&radius={radius}"
    
    # Add date filter
    url += f"&fromage={days_ago if days_ago in VALID_DAYS_AGO else 7}"
    
    # Add work setting filter
    if work_setting and work_setting in WORK_SETTING_FILTERS:
        url += WORK_SETTING_FILTERS[work_setting]
    
    # Add job type filter
    if job_type and job_type.lower() in JOB_TYPE_FILTERS:
        url += JOB_TYPE_FILTERS[job_type.lower()]
    
    return url


def find_element_with_retry(card: WebElement, selectors: List[Tuple[str, str]]) -> Optional[WebElement]:
    """Find an element using multiple selectors with retry."""
    for selector_type, selector in selectors:
        try:
            return card.find_element(selector_type, selector)
        except NoSuchElementException:
            continue
    return None


def extract_job_data(card: WebElement) -> Optional[Dict[str, Any]]:
    """Extract information from a job card."""
    try:
        job_data = {}
        
        # Required fields
        required_fields = ['title', 'company', 'link']
        
        # Extract all fields
        for field, selectors in JOB_FIELD_SELECTORS.items():
            element = find_element_with_retry(card, selectors)
            
            if not element:
                if field in required_fields:
                    return None
                job_data[field] = None
                continue
                
            if field == 'link':
                original_url = element.get_attribute('href')
                
                # Check if it's an ad (contains pagead in the URL)
                job_data['is_ad'] = 'pagead' in original_url
                
                # Extract job ID from URL
                job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', original_url)
                if job_id_match:
                    job_id = job_id_match.group(1)
                    job_data['job_id'] = job_id
                    # Create a simplified URL using the job ID
                    job_data[field] = f"https://www.indeed.com/viewjob?jk={job_id}"
                else:
                    # Keep the original URL if we can't find a job ID
                    job_data[field] = original_url
                    job_data['job_id'] = None
            else:
                # Some job titles use the 'title' attribute
                if field == 'title' and element.get_attribute('title'):
                    job_data[field] = element.get_attribute('title')
                else:
                    job_data[field] = element.text.strip()
        
        # Validate required fields
        if not all(job_data.get(field) for field in required_fields):
            return None
            
        return job_data
        
    except Exception as e:
        logger.debug(f"Failed to scrape job card: {e}")
        return None


def scrape_job_listings(
    driver: uc.Chrome,
    job_title: str,
    location: str = "",
    search_radius: Optional[int] = None,
    max_pages: int = 3,
    days_ago: int = 7,
    work_setting: Optional[str] = None,
    job_type: Optional[str] = None,
    include_descriptions: bool = False
) -> List[JobListing]:
    """Main function to scrape Indeed job listings."""
    if SHOULD_EXIT:
        return []
    
    try:
        # Build and navigate to search URL
        search_url = get_search_url(
            job_title, location, search_radius, days_ago, work_setting, job_type
        )
        logger.info(f"Searching for jobs: {search_url}")
        driver.get(search_url)
        random_delay()
        
        # Handle CAPTCHA
        logger.info("\nIf a CAPTCHA appears, please solve it and press Enter to continue...")
        if get_user_input() is None:
            return []
        time.sleep(2)
        
        # Prepare for scraping
        all_jobs = []
        job_ids = set()
        title_company_pairs = set()
        
        # Scrape pages
        for page in range(1, max_pages + 1):
            if SHOULD_EXIT:
                break
                
            logger.info(f"Scraping page {page} of {max_pages}...")
            scroll_page(driver)
            
            # Find job cards
            job_cards = driver.find_elements(By.CSS_SELECTOR, JOB_CARD_SELECTOR)
            if not job_cards:
                logger.info("No job cards found on this page.")
                break
                
            # Process each job card
            jobs_on_page = []
            page_urls_to_scrape = []
            
            for card in job_cards:
                if SHOULD_EXIT:
                    break
                    
                job_data = extract_job_data(card)
                if not job_data:
                    continue
                    
                # Check for duplicates
                job_id = job_data.get('job_id', '')
                title_company = f"{job_data['title']}_{job_data['company']}"
                
                if (job_id and job_id in job_ids) or (title_company in title_company_pairs):
                    continue
                    
                # Add to tracking sets
                if job_id:
                    job_ids.add(job_id)
                title_company_pairs.add(title_company)
                
                # Create JobListing
                job_listing = JobListing(
                    title=job_data['title'],
                    company=job_data['company'],
                    location=job_data.get('location'),
                    salary=job_data.get('salary'),
                    job_url=job_data.get('link'),
                    job_id=job_data.get('job_id'),
                    job_type=job_data.get('job_type'),
                    work_setting=job_data.get('work_setting'),
                    search_url=search_url,
                    is_ad=job_data.get('is_ad', False)
                )
                
                jobs_on_page.append(job_listing)
                
                # Track URLs for description scraping
                if include_descriptions and job_data.get('link'):
                    page_urls_to_scrape.append(job_data['link'])
                
                random_delay(0.2, 0.5)
            
            logger.info(f"Found {len(jobs_on_page)} unique jobs on this page")
            
            # Batch scrape descriptions if needed
            if include_descriptions and page_urls_to_scrape:
                logger.info(f"Scraping descriptions for {len(page_urls_to_scrape)} jobs...")
                url_to_listing = {listing.job_url: listing for listing in jobs_on_page if listing.job_url}
                batch_scrape_descriptions(driver, url_to_listing)
            
            all_jobs.extend(jobs_on_page)
            
            # Check if we should continue to the next page
            if SHOULD_EXIT or page >= max_pages:
                break
                
            if not navigate_to_next_page(driver):
                break
                
            random_delay(2.0, 4.0)
        
        logger.info(f"Scraped {len(all_jobs)} unique jobs total")
        return all_jobs
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        return []


# =====================
# Command-line Interface
# =====================
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape job listings from Indeed.com",
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
        help="Location for job search (e.g., 'New York, NY' or '90210')"
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
        "--work-setting", 
        type=str, 
        choices=list(WORK_SETTING_FILTERS.keys()),
        default=None,
        help="Filter for work setting: remote, hybrid, or onsite jobs"
    )
    
    parser.add_argument(
        "--job-type", 
        type=str, 
        choices=list(JOB_TYPE_FILTERS.keys()),
        default=None,
        help="Filter by job type"
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        default=None,
        help="Output CSV file path (default: auto-generated)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--exclude-descriptions", 
        action="store_true",
        help="Skip scraping full job descriptions"
    )
    
    parser.add_argument(
        "--keep-browser", 
        action="store_true",
        help="Keep the browser open after scraping is complete"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point for the Indeed job scraper."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)
    
    try:
        # Parse arguments
        args = parse_args()
        
        # Configure logging
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        
        # Create data directories
        ensure_data_dirs()
        
        # Initialize browser
        driver = setup_browser()
        
        try:
            # Get output filepath
            output_file = Path(args.output) if args.output else get_output_filepath(args.job_title, args.location)
            
            # Perform scraping
            logger.info(f"Starting job search for '{args.job_title}' in {args.location or 'any location'}")
            
            jobs = scrape_job_listings(
                driver=driver,
                job_title=args.job_title,
                location=args.location,
                search_radius=args.search_radius,
                max_pages=args.num_pages,
                days_ago=args.days_ago,
                work_setting=args.work_setting,
                job_type=args.job_type,
                include_descriptions=not args.exclude_descriptions
            )
            
            # Save results
            if jobs:
                export_jobs_to_csv(jobs, output_file)
            else:
                logger.info("No jobs were found.")
                
            # Keep browser open if requested
            if args.keep_browser:
                logger.info("\nBrowser kept open. Press Enter to close...")
                input()
                
        finally:
            # Clean up
            if not args.keep_browser:
                try:
                    driver.quit()
                except Exception:
                    pass
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1
    
    return 0 if not SHOULD_EXIT else 130


if __name__ == "__main__":
    sys.exit(main())