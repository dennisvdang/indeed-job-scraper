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
from typing import Optional, List, Dict, Tuple, Any
import html2text

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
    Clean HTML content from job descriptions to make it more readable using html2text.
    
    Args:
        html_content: Raw HTML content from the job description
        
    Returns:
        Cleaned text version of the job description
    """
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


def extract_posted_date(driver: uc.Chrome) -> Optional[str]:
    """
    Extract the exact job posting date from the page.
    
    Args:
        driver: Chrome driver instance
        
    Returns:
        The exact posted date as a string, or None if not found
    """
    try:
        # Check for meta tags containing date information
        date_meta_selectors = [
            "meta[itemprop='datePosted']",
            "meta[property='datePosted']",
            "meta[name='date']",
            "meta[property='article:published_time']"
        ]
        
        for selector in date_meta_selectors:
            try:
                date_element = driver.find_element(By.CSS_SELECTOR, selector)
                if date_element:
                    content = date_element.get_attribute("content")
                    if content and (re.match(r'\d{4}-\d{2}-\d{2}', content) or 'T' in content):
                        logger.debug(f"Found exact date in meta tag: {content}")
                        return content
            except NoSuchElementException:
                continue
                
        # If meta tags failed, try to find structured data in script tags
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
                    # Navigate nested JSON structures
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and ('datePosted' in item or 'datePublished' in item):
                                date = item.get('datePosted') or item.get('datePublished')
                                if date:
                                    logger.debug(f"Found exact date in structured data: {date}")
                                    return date
                    elif isinstance(data, dict):
                        date = data.get('datePosted') or data.get('datePublished')
                        if date:
                            logger.debug(f"Found exact date in structured data: {date}")
                            return date
            except Exception as e:
                logger.debug(f"Error parsing script content: {str(e)}")
                continue
                
        return None
    except Exception as e:
        logger.debug(f"Error extracting exact date: {str(e)}")
        return None


def scrape_job_description(driver: uc.Chrome, job_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Navigate to a job details page and scrape the job description and posted date.
    
    Args:
        driver: Chrome driver instance
        job_url: URL to the job details page
        
    Returns:
        A tuple of (job_description, posted_date) where both can be None if not found
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
        
        # Clean HTML from description if needed
        cleaned_description = None
        if description_text:
            cleaned_description = clean_html_description(description_text)
            
        # Return to search results page
        driver.get(current_url)
        random_delay(1.0, 2.0)
        
        if not cleaned_description:
            logger.warning(f"Could not find job description on page: {job_url}")
            
        return cleaned_description, exact_date
        
    except Exception as e:
        logger.error(f"Error scraping job description: {str(e)}")
        # Try to return to search results on error
        try:
            driver.get(current_url)
            random_delay(1.0, 2.0)
        except:
            pass
        return None, None


def batch_scrape_descriptions(
    driver: uc.Chrome, 
    job_urls: List[str], 
    max_retries: int = 2,
    delay_between_jobs: Tuple[float, float] = (1.5, 3.0)
) -> Dict[str, str]:
    """
    Scrape descriptions and posted dates for multiple jobs with resilience features.
    
    Args:
        driver: Chrome driver instance
        job_urls: List of job URLs to scrape descriptions from
        max_retries: Maximum number of retry attempts per job
        delay_between_jobs: Tuple of (min, max) seconds to delay between jobs
        
    Returns:
        Dictionary mapping job URLs to their descriptions and posted dates.
        URLs ending with "_posted_date" contain posting date information.
    """
    results = {}
    
    total_jobs = len(job_urls)
    logger.info(f"Batch scraping {total_jobs} job descriptions")
    
    for i, url in enumerate(job_urls):
        logger.info(f"Processing job {i+1}/{total_jobs}: {url}")
        
        # Try with retries
        description = None
        posted_date = None
        attempts = 0
        
        while description is None and attempts <= max_retries:
            if attempts > 0:
                logger.debug(f"Retry attempt {attempts}/{max_retries} for {url}")
                # Longer delay between retries
                random_delay(3.0, 5.0)
                
            description, posted_date = scrape_job_description(driver, url)
            attempts += 1
            
        # Add description to results
        results[url] = description
        
        # Add posted date to results if available
        if posted_date:
            results[f"{url}_posted_date"] = posted_date
            logger.debug(f"Extracted posted date: {posted_date}")
        
        # Random delay between jobs to avoid rate limiting
        if i < total_jobs - 1:  # No need to delay after the last job
            min_delay, max_delay = delay_between_jobs
            random_delay(min_delay, max_delay)
    
    # Count actual job descriptions (not posted dates)
    success_count = sum(1 for key in results.keys() if not key.endswith('_posted_date') and results[key] is not None)
    logger.info(f"Successfully scraped {success_count}/{total_jobs} job descriptions")
    
    return results


if __name__ == "__main__":
    """For testing the module functionality."""
    logger.info("This module is designed to be imported by indeed_scraper.py")
    logger.info("Direct execution is only supported for development/testing") 