#!/usr/bin/env python3
"""
Indeed Job Description Scraper

A module for extracting detailed job descriptions from Indeed.com job listings.
This module works in conjunction with the indeed_scraper.py main module but can
also be used independently for focused description scraping tasks.

Author: Dennis
"""

import re
import time
import random
import logging
from typing import Optional, List, Dict, Tuple

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("description_scraper")


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Add a random delay to simulate human behavior and avoid being detected as a bot.
    
    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def clean_html_description(html_content: str) -> str:
    """
    Clean HTML content from job descriptions to make it more readable.
    
    Args:
        html_content: Raw HTML content from the job description
        
    Returns:
        Cleaned text version of the job description
    """
    if not html_content:
        return ""
    
    # Replace common HTML tags with line breaks or spaces
    replacements = [
        ('<br\\s*/?>', '\n'),                   # Line breaks
        ('</?p>', '\n\n'),                      # Paragraphs
        ('<li\\s*/?>', '\n• '),                 # List items
        ('</?ul>', '\n'),                       # Unordered lists
        ('</?ol>', '\n'),                       # Ordered lists
        ('<h\\d[^>]*>', '\n\n'),                # Headers start
        ('</h\\d>', '\n'),                      # Headers end
        ('<div[^>]*>', '\n'),                   # Divs
        ('</div>', '\n'),                       # End divs
        ('<[^>]*>', ' '),                       # All other tags
    ]
    
    text = html_content
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Fix whitespace issues
    text = re.sub(r'\s+', ' ', text)            # Collapse multiple spaces
    text = re.sub(r'\n\s+', '\n', text)         # Remove spaces after newlines
    text = re.sub(r'\n{3,}', '\n\n', text)      # Limit consecutive newlines
    
    # Fix common HTML entities
    html_entities = [
        ('&nbsp;', ' '),
        ('&amp;', '&'),
        ('&lt;', '<'),
        ('&gt;', '>'),
        ('&quot;', '"'),
        ('&apos;', "'"),
        ('&#39;', "'"),
        ('&ndash;', '–'),
        ('&mdash;', '—'),
        ('&bull;', '•'),
        ('&#8226;', '•'),
    ]
    
    for entity, replacement in html_entities:
        text = text.replace(entity, replacement)
    
    # Remove remaining HTML entities
    text = re.sub(r'&[a-zA-Z0-9]+;', '', text)
    
    # Strip extra whitespace at start and end
    text = text.strip()
    
    return text


def scrape_job_description(driver: uc.Chrome, job_url: str) -> Optional[str]:
    """
    Navigate to a job details page and scrape the job description.
    
    Args:
        driver: Chrome driver instance
        job_url: URL to the job details page
        
    Returns:
        Job description as text or None if failed
    """
    try:
        logger.debug(f"Navigating to job details: {job_url}")
        
        # Store the current URL to return to search results later
        current_url = driver.current_url
        
        # Navigate to job URL
        driver.get(job_url)
        random_delay(2.0, 3.0)  # Wait for page to load
        
        # Try to locate the job description element
        description_selectors = [
            (By.ID, "jobDescriptionText"),  # Most common
            (By.CSS_SELECTOR, "[data-testid='jobDescriptionText']"),  # New UI
            (By.CSS_SELECTOR, "div.jobsearch-jobDescriptionText"),  # Older UI
            (By.CSS_SELECTOR, "div.job-description")  # Generic fallback
        ]
        
        description_text = None
        for selector_type, selector in description_selectors:
            try:
                # Wait for element to be present
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector))
                )
                description_element = driver.find_element(selector_type, selector)
                description_text = description_element.get_attribute('innerHTML')
                if description_text:
                    break
            except (NoSuchElementException, TimeoutException):
                continue
        
        # Clean HTML from description if needed
        if description_text:
            # Return to search results page
            driver.get(current_url)
            random_delay(1.0, 2.0)
            return clean_html_description(description_text)
        else:
            logger.warning(f"Could not find job description on page: {job_url}")
            
        # Return to search results page
        driver.get(current_url)
        random_delay(1.0, 2.0)
        return None
        
    except Exception as e:
        logger.error(f"Error scraping job description: {str(e)}")
        # Try to return to search results on error
        try:
            driver.get(current_url)
            random_delay(1.0, 2.0)
        except:
            pass
        return None


def batch_scrape_descriptions(
    driver: uc.Chrome, 
    job_urls: List[str], 
    max_retries: int = 2,
    delay_between_jobs: Tuple[float, float] = (1.5, 3.0)
) -> Dict[str, Optional[str]]:
    """
    Scrape descriptions for multiple jobs with resilience features.
    
    Args:
        driver: Chrome driver instance
        job_urls: List of job URLs to scrape descriptions from
        max_retries: Maximum number of retry attempts per job
        delay_between_jobs: Tuple of (min, max) seconds to delay between jobs
        
    Returns:
        Dictionary mapping job URLs to their descriptions (or None if failed)
    """
    results = {}
    
    total_jobs = len(job_urls)
    logger.info(f"Batch scraping {total_jobs} job descriptions")
    
    for i, url in enumerate(job_urls):
        logger.info(f"Processing job {i+1}/{total_jobs}: {url}")
        
        # Try with retries
        description = None
        attempts = 0
        
        while description is None and attempts <= max_retries:
            if attempts > 0:
                logger.debug(f"Retry attempt {attempts}/{max_retries} for {url}")
                # Longer delay between retries
                random_delay(3.0, 5.0)
                
            description = scrape_job_description(driver, url)
            attempts += 1
            
        results[url] = description
        
        # Random delay between jobs to avoid rate limiting
        if i < total_jobs - 1:  # No need to delay after the last job
            min_delay, max_delay = delay_between_jobs
            random_delay(min_delay, max_delay)
    
    success_count = sum(1 for desc in results.values() if desc is not None)
    logger.info(f"Successfully scraped {success_count}/{total_jobs} job descriptions")
    
    return results


if __name__ == "__main__":
    """Simple demonstration/test when module is run directly."""
    import argparse
    import sys
    import os
    
    # Add parent directory to path so we can import from src.indeed_scraper
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    parser = argparse.ArgumentParser(
        description="Scrape job descriptions from Indeed.com URLs"
    )
    parser.add_argument(
        "urls", 
        nargs="+", 
        help="One or more Indeed job URLs to scrape"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable detailed logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        from indeed_scraper import setup_browser
        
        driver = setup_browser()
        try:
            results = batch_scrape_descriptions(driver, args.urls)
            
            for url, description in results.items():
                print(f"\n{'=' * 80}\n{url}\n{'-' * 80}")
                if description:
                    print(description[:500] + "..." if len(description) > 500 else description)
                else:
                    print("Failed to scrape description")
                print(f"{'=' * 80}\n")
                
        finally:
            driver.quit()
            
    except ImportError:
        logger.error("Failed to import setup_browser from indeed_scraper")
        logger.error("Make sure indeed_scraper.py is in the same directory") 