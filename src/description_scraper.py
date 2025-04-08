#!/usr/bin/env python3
"""
Indeed Job Description Scraper

A module for extracting detailed job descriptions and job posting dates from Indeed.com job listings.

Author: Dennis
"""

import re
import time
import random
import logging
from typing import Optional, List, Dict, Tuple, Any, Union
import html2text

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

try:
    from indeed_scraper import JobListing
except ImportError:
    JobListing = Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("description_scraper")


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Add a random delay to simulate human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def clean_html_description(html_content: str) -> str:
    """Clean HTML content from job descriptions to make it more readable using html2text."""
    if not html_content:
        return ""
    
    # Configure html2text
    h = html2text.HTML2Text()
    h.ignore_links = True  # Don't show URLs, just link text
    h.ignore_images = True  # Don't show image URLs
    h.ignore_emphasis = True  # Don't show bold/italic markers
    h.body_width = 0  # Don't wrap text at specific width
    h.unicode_snob = True  # Use Unicode characters instead of ASCII approximations
    h.ul_item_mark = "•"  # Use bullet points for unordered lists
    
    # Convert HTML to clean text
    text = h.handle(html_content)
    
    # Clean up extra whitespace
    text = re.sub(r'\n\s+\n', '\n\n', text)  # Remove extra blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)   # Limit consecutive newlines
    text = text.strip()  # Remove leading/trailing whitespace
    
    return text


def extract_job_details(driver: uc.Chrome) -> Dict[str, Optional[str]]:
    """
    Extract detailed job information from the job details section including job type and work setting.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        Dictionary containing job details (job_type, work_setting)
    """
    job_details = {
        'job_type': None,
        'work_setting': None
    }
    
    try:
        # Find job details section
        job_details_selectors = [
            (By.ID, "jobDetailsSection"),
            (By.CSS_SELECTOR, "[data-testid='jobDetails']"),
            (By.CSS_SELECTOR, "div.jobsearch-JobDescriptionSection-sectionItem")
        ]
        
        # Try each selector to find the job details section
        job_details_section = None
        for selector_type, selector in job_details_selectors:
            try:
                job_details_section = driver.find_element(selector_type, selector)
                if job_details_section:
                    break
            except NoSuchElementException:
                continue
        
        if not job_details_section:
            logger.debug("Could not find job details section")
            return job_details
            
        # Extract job type
        try:
            # Look for job type heading
            job_type_heading = job_details_section.find_element(By.XPATH, ".//h3[contains(text(), 'Job type')]")
            if job_type_heading:
                # Get the job type value from the nearest span element
                job_type_item = job_type_heading.find_element(By.XPATH, "../..//span[contains(@class, 'e1wnkr790')]")
                if job_type_item:
                    job_details['job_type'] = job_type_item.text.strip()
                    logger.debug(f"Found job type: {job_details['job_type']}")
        except NoSuchElementException:
            logger.debug("Could not find job type information")
            
        # Extract work setting
        try:
            # Look for work setting heading
            work_setting_heading = job_details_section.find_element(By.XPATH, ".//h3[contains(text(), 'Work setting')]")
            if work_setting_heading:
                # Get the work setting value from the nearest span element
                work_setting_item = work_setting_heading.find_element(By.XPATH, "../..//span[contains(@class, 'e1wnkr790')]")
                if work_setting_item:
                    job_details['work_setting'] = work_setting_item.text.strip()
                    logger.debug(f"Found work setting: {job_details['work_setting']}")
        except NoSuchElementException:
            logger.debug("Could not find work setting information")
            
        return job_details
        
    except Exception as e:
        logger.debug(f"Error extracting job details: {str(e)}")
        return job_details


def extract_posted_date(driver: uc.Chrome) -> Optional[str]:
    """
    Extract the exact job posting date from the page and format it as YYYY-MM-DD.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        The posted date as a string in YYYY-MM-DD format, or None if not found
    """
    def format_date(date_str: str) -> str:
        """Format date string to YYYY-MM-DD format."""
        try:
            from datetime import datetime
            # Parse ISO 8601 format and convert to YYYY-MM-DD
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            return date_str
    
    try:
        # Check for meta tags containing date information
        date_meta_selectors = [
            "meta[itemprop='datePosted']",
            "meta[property='datePosted']",
            "meta[name='date']",
            "meta[property='article:published_time']"
        ]
        
        # Try to find date in meta tags
        for selector in date_meta_selectors:
            try:
                date_element = driver.find_element(By.CSS_SELECTOR, selector)
                content = date_element.get_attribute("content")
                if content and (re.match(r'\d{4}-\d{2}-\d{2}', content) or 'T' in content):
                    logger.debug(f"Found exact date in meta tag: {content}")
                    return format_date(content)
            except NoSuchElementException:
                continue
                
        # Try to find structured data in script tags
        script_elements = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        for script in script_elements:
            try:
                content = script.get_attribute('innerHTML')
                if not content:
                    continue
                    
                # Check if content contains datePosted field
                if '"datePosted":' in content or '"datePublished":' in content:
                    import json
                    data = json.loads(content)
                    
                    # Check for date in the data structure
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                date = item.get('datePosted') or item.get('datePublished')
                                if date:
                                    logger.debug(f"Found exact date in structured data: {date}")
                                    return format_date(date)
                    elif isinstance(data, dict):
                        date = data.get('datePosted') or data.get('datePublished')
                        if date:
                            logger.debug(f"Found exact date in structured data: {date}")
                            return format_date(date)
            except Exception as e:
                logger.debug(f"Error parsing script content: {str(e)}")
                
        return None
    except Exception as e:
        logger.debug(f"Error extracting exact date: {str(e)}")
        return None


def scrape_job_description(
    driver: uc.Chrome, 
    job_url: str,
    need_job_details: bool = False
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Optional[str]]]]:
    """
    Navigate to a job details page and scrape the job description, posted date, and job details.
    
    Args:
        driver: Chrome driver instance
        job_url: URL to the job details page
        need_job_details: Whether to extract job details (job type and work setting)
        
    Returns:
        A tuple of (job_description, posted_date, job_details) where all can be None if not found
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
        
        # Extract the exact posting date
        exact_date = extract_posted_date(driver)
        
        # Extract job details if requested
        job_details = None
        if need_job_details:
            job_details = extract_job_details(driver)
        
        # Clean HTML from description if needed
        cleaned_description = None
        if description_text:
            cleaned_description = clean_html_description(description_text)
            
        # Return to search results page
        driver.get(current_url)
        random_delay(1.0, 2.0)
        
        if not cleaned_description:
            logger.warning(f"Could not find job description on page: {job_url}")
            
        return cleaned_description, exact_date, job_details
        
    except Exception as e:
        logger.error(f"Error scraping job description: {str(e)}")
        # Try to return to search results on error
        try:
            driver.get(current_url)
            random_delay(1.0, 2.0)
        except:
            pass
        return None, None, None


def batch_scrape_descriptions(
    driver: uc.Chrome, 
    job_listings_map: Dict[str, JobListing],
    max_retries: int = 2,
    delay_between_jobs: Tuple[float, float] = (1.5, 3.0)
) -> None:
    """
    Scrape descriptions and posted dates for multiple jobs and update JobListing objects.
    
    Args:
        driver: Chrome driver instance
        job_listings_map: Dictionary mapping job URLs to their JobListing objects
        max_retries: Maximum number of retry attempts per job
        delay_between_jobs: Tuple of (min, max) seconds to delay between jobs
    """
    if not job_listings_map:
        return
    
    job_urls = list(job_listings_map.keys())
    total_jobs = len(job_urls)
    logger.info(f"Batch scraping {total_jobs} job descriptions")
    
    success_count = 0
    
    for i, url in enumerate(job_urls):
        logger.info(f"Processing job {i+1}/{total_jobs}: {url}")
        job_listing = job_listings_map[url]
        
        # Try with retries
        description = None
        attempts = 0
        
        while description is None and attempts <= max_retries:
            if attempts > 0:
                logger.debug(f"Retry attempt {attempts}/{max_retries} for {url}")
                # Longer delay between retries
                random_delay(3.0, 5.0)
                
            # Always extract job details when accessing job page for descriptions
            description, posted_date, job_details = scrape_job_description(driver, url, need_job_details=True)
            attempts += 1
            
        # Update the JobListing object with scraped data
        if description:
            job_listing.description = description
            success_count += 1
            
        if posted_date:
            job_listing.date_posted = posted_date
            
        if job_details:
            if job_details.get('job_type'):
                job_listing.job_type = job_details['job_type']
                
            if job_details.get('work_setting'):
                job_listing.work_setting = job_details['work_setting']
        
        # Random delay between jobs to avoid rate limiting
        if i < total_jobs - 1:  # No need to delay after the last job
            min_delay, max_delay = delay_between_jobs
            random_delay(min_delay, max_delay)
    
    logger.info(f"Successfully scraped {success_count}/{total_jobs} job descriptions")


if __name__ == "__main__":
    """For testing the module functionality."""
    logger.info("This module is designed to be imported by indeed_scraper.py")