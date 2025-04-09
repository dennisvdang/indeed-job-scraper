#!/usr/bin/env python3
"""
Indeed Job Description Scraper

A module for extracting job descriptions and posting dates from Indeed.com job listings.

Author: Dennis
"""

import json
import logging
import random
import re
import threading
import time
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Any, Union

import html2text
import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

# =====================
# Utility Functions
# =====================
def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """Add a random delay to simulate human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def clean_html_description(html_content: str) -> str:
    """Convert HTML job description to clean readable text."""
    if not html_content:
        return ""
    
    # Configure html2text
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_emphasis = True
    h.body_width = 0
    h.unicode_snob = True
    h.ul_item_mark = "•"
    
    # Convert and clean
    text = h.handle(html_content)
    text = re.sub(r'\n\s+\n', '\n\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def format_date(date_str: str) -> str:
    """Format ISO date string to YYYY-MM-DD format."""
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_str


# =====================
# Extraction Functions
# =====================
def extract_job_details(driver: uc.Chrome) -> Dict[str, Optional[str]]:
    """Extract job type and work setting information from job details section."""
    job_details = {'job_type': None, 'work_setting': None}
    
    try:
        # Find job details section
        selectors = [
            (By.ID, "jobDetailsSection"),
            (By.CSS_SELECTOR, "[data-testid='jobDetails']"),
            (By.CSS_SELECTOR, "div.jobsearch-JobDescriptionSection-sectionItem")
        ]
        
        # Try each selector
        section = None
        for selector_type, selector in selectors:
            try:
                section = driver.find_element(selector_type, selector)
                if section:
                    break
            except NoSuchElementException:
                continue
        
        if not section:
            return job_details
            
        # Extract job type and work setting
        for field, heading_text in [('job_type', 'Job type'), ('work_setting', 'Work setting')]:
            try:
                heading = section.find_element(By.XPATH, f".//h3[contains(text(), '{heading_text}')]")
                value_element = heading.find_element(By.XPATH, "../..//span[contains(@class, 'e1wnkr790')]")
                job_details[field] = value_element.text.strip()
            except NoSuchElementException:
                pass
            
        return job_details
        
    except Exception as e:
        logger.debug(f"Error extracting job details: {e}")
        return job_details


def extract_posted_date(driver: uc.Chrome) -> Optional[str]:
    """Extract job posting date from page and format as YYYY-MM-DD."""
    try:
        # Try meta tags first
        meta_selectors = [
            "meta[itemprop='datePosted']",
            "meta[property='datePosted']",
            "meta[name='date']",
            "meta[property='article:published_time']"
        ]
        
        for selector in meta_selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                content = element.get_attribute("content")
                if content and (re.match(r'\d{4}-\d{2}-\d{2}', content) or 'T' in content):
                    return format_date(content)
            except NoSuchElementException:
                continue
                
        # Try structured data in script tags
        scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        for script in scripts:
            try:
                content = script.get_attribute('innerHTML')
                if not content or not ('"datePosted":' in content or '"datePublished":' in content):
                    continue
                    
                data = json.loads(content)
                
                # Check data structure
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            date = item.get('datePosted') or item.get('datePublished')
                            if date:
                                return format_date(date)
                elif isinstance(data, dict):
                    date = data.get('datePosted') or data.get('datePublished')
                    if date:
                        return format_date(date)
            except Exception:
                pass
                
        return None
    except Exception:
        return None


def scrape_job_description(
    driver: uc.Chrome, 
    job_url: str,
    need_job_details: bool = False
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Optional[str]]]]:
    """
    Navigate to a job page and extract description, posting date, and job details.
    
    Args:
        driver: Chrome driver instance
        job_url: URL to the job details page
        need_job_details: Whether to extract job type and work setting
        
    Returns:
        Tuple of (description, posted_date, job_details)
    """
    try:
        # Store current URL
        current_url = driver.current_url
        
        # Normalize the URL to the simplified format if it's not already
        job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_url)
        if job_id_match:
            job_id = job_id_match.group(1)
            normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
        else:
            normalized_url = job_url
            
        # Navigate to job page
        driver.get(normalized_url)
        random_delay(2.0, 3.0)
        
        # For ad URLs that redirect, extract job ID from the redirected URL
        if not job_id_match and "pagead" in job_url:
            redirected_url = driver.current_url
            job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', redirected_url)
            if job_id_match:
                job_id = job_id_match.group(1)
                normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                logger.info(f"Extracted job ID {job_id} from ad URL redirect")
        
        # Find job description
        description_selectors = [
            (By.ID, "jobDescriptionText"),
            (By.CSS_SELECTOR, "[data-testid='jobDescriptionText']"),
            (By.CSS_SELECTOR, "div.jobsearch-jobDescriptionText"),
            (By.CSS_SELECTOR, "div.job-description")
        ]
        
        # Try each selector
        description_text = None
        for selector_type, selector in description_selectors:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector))
                )
                element = driver.find_element(selector_type, selector)
                description_text = element.get_attribute('innerHTML')
                if description_text:
                    break
            except (NoSuchElementException, TimeoutException):
                continue
        
        # Extract date and job details
        posted_date = extract_posted_date(driver)
        job_details = extract_job_details(driver) if need_job_details else None
        
        # Clean HTML description
        cleaned_description = clean_html_description(description_text) if description_text else None
            
        # Return to original page
        driver.get(current_url)
        random_delay(1.0, 2.0)
        
        return cleaned_description, posted_date, job_details
        
    except Exception as e:
        logger.error(f"Error scraping job description: {e}")
        try:
            driver.get(current_url)
            random_delay(1.0, 2.0)
        except:
            pass
        return None, None, None


def batch_scrape_descriptions(
    driver: uc.Chrome, 
    job_listings_map: Dict[str, JobListing],
    max_retries: int = 0,
    delay_between_jobs: Tuple[float, float] = (1.5, 3.0),
    timeout_per_job: float = 15.0
) -> None:
    """
    Scrape descriptions for multiple jobs and update JobListing objects.
    
    Args:
        driver: Chrome driver instance
        job_listings_map: Dictionary mapping job URLs to JobListing objects
        max_retries: Number of retry attempts per job
        delay_between_jobs: Delay between job requests
        timeout_per_job: Maximum time in seconds to spend on each job
    """
    if not job_listings_map:
        return
    
    job_urls = list(job_listings_map.keys())
    total_jobs = len(job_urls)
    logger.info(f"Batch scraping {total_jobs} job descriptions")
    
    success_count = 0
    
    for i, url in enumerate(job_urls):
        job_listing = job_listings_map[url]
        
        # Normalize URL if needed (ensures job_listing also gets the normalized URL)
        job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', url)
        if job_id_match:
            job_id = job_id_match.group(1)
            normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
            # Update the job_listing with the normalized URL
            job_listing.job_url = normalized_url
            url = normalized_url
        
        logger.info(f"Processing job {i+1}/{total_jobs}: {job_listing.title} (URL: {url})")
        
        # Scrape job details
        description, posted_date, job_details = scrape_job_description(
            driver, url, need_job_details=True
        )
        
        # Check if we got redirected to a job page with a job ID (for ad URLs)
        if "pagead" in url and not job_id_match:
            current_url = driver.current_url
            job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', current_url)
            if job_id_match:
                job_id = job_id_match.group(1)
                normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                # Update the job listing with the job ID and normalized URL
                job_listing.job_url = normalized_url
                job_listing.job_id = job_id
                # Ensure the is_ad flag is set for these URLs
                job_listing.is_ad = True
                logger.info(f"Updated ad URL to simplified URL: {normalized_url}")
            
        # Update the JobListing object
        if description:
            job_listing.description = description
            success_count += 1
            logger.info(f"✓ Got description for {job_listing.title}")
        else:
            logger.info(f"✗ No description found for {job_listing.title}")
            
        # Update other fields if available
        if posted_date:
            job_listing.date_posted = posted_date
            
        if job_details:
            if job_details.get('job_type'):
                job_listing.job_type = job_details['job_type']
                
            if job_details.get('work_setting'):
                job_listing.work_setting = job_details['work_setting']
        
        # Random delay between jobs (except after the last one)
        if i < total_jobs - 1:
            min_delay, max_delay = delay_between_jobs
            random_delay(min_delay, max_delay)
    
    logger.info(f"Successfully scraped {success_count}/{total_jobs} job descriptions")


if __name__ == "__main__":
    logger.info("This module is designed to be imported by indeed_scraper.py")