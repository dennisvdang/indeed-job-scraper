#!/usr/bin/env python3
"""Job description scraping functionality."""

import json
import re
import time
from typing import Dict, Optional, Tuple, List, Callable, Any
from datetime import datetime

import html2text
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

from .models import JobListing
from .config import config
from .logger import logger
from .browser import random_delay, handle_possible_captcha
from .data.cleaners import clean_html_description

def format_date(date_str: str) -> str:
    """
    Format ISO date string to YYYY-MM-DD format.
    
    Args:
        date_str: Date string to format
        
    Returns:
        Formatted date string
    """
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return date_str

def extract_job_details(driver: uc.Chrome) -> Dict[str, Optional[str]]:
    """
    Extract job type and work setting information from job details section.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        Dictionary with job details
    """
    job_details = {'job_type': None, 'work_setting': None}
    
    try:
        selectors = [
            (By.ID, "jobDetailsSection"),
            (By.CSS_SELECTOR, "[data-testid='jobDetails']"),
            (By.CSS_SELECTOR, "div.jobsearch-JobDescriptionSection-sectionItem")
        ]
        
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
    """
    Extract job posting date from page and format as YYYY-MM-DD.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        Posting date string or None
    """
    try:
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
                
        scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        for script in scripts:
            try:
                content = script.get_attribute('innerHTML')
                if not content or not ('"datePosted":' in content or '"datePublished":' in content):
                    continue
                    
                data = json.loads(content)
                
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
    except Exception as e:
        logger.debug(f"Error extracting posted date: {e}")
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
    current_url = driver.current_url
    
    try:
        job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_url)
        normalized_url = f"https://www.indeed.com/viewjob?jk={job_id_match.group(1)}" if job_id_match else job_url
            
        driver.get(normalized_url)
        random_delay(2.0, 3.0)
        
        # For URLs that redirect, extract job ID from the redirected URL
        if not job_id_match and "pagead" in job_url:
            redirected_url = driver.current_url
            job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', redirected_url)
            if job_id_match:
                job_id = job_id_match.group(1)
                normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                logger.info(f"Extracted job ID {job_id} from ad URL redirect")
        
        description_selectors = [
            (By.ID, "jobDescriptionText"),
            (By.CSS_SELECTOR, "[data-testid='jobDescriptionText']"),
            (By.CSS_SELECTOR, "div.jobsearch-jobDescriptionText"),
            (By.CSS_SELECTOR, "div.job-description")
        ]
        
        description_text = None
        for selector_type, selector in description_selectors:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((selector_type, selector)))
                element = driver.find_element(selector_type, selector)
                description_text = element.get_attribute('innerHTML')
                if description_text:
                    break
            except (NoSuchElementException, TimeoutException):
                continue
        
        # Extract date and job details
        posted_date = extract_posted_date(driver)
        job_details = extract_job_details(driver) if need_job_details else None
        cleaned_description = clean_html_description(description_text) if description_text else None
        
        return cleaned_description, posted_date, job_details
        
    except Exception as e:
        logger.error(f"Error scraping job description: {e}")
        return None, None, None
    finally:
        try:
            driver.get(current_url)
            random_delay(1.0, 2.0)
        except Exception as e:
            logger.error(f"Error navigating back to original URL: {e}")

def batch_scrape_descriptions(
    driver: uc.Chrome, 
    job_listings: List[JobListing],
    input_prompt: Callable = input
) -> List[JobListing]:
    """
    Scrape descriptions for multiple jobs and update JobListing objects.
    
    Args:
        driver: Chrome driver instance
        job_listings: List of JobListing objects to update
        input_prompt: Function to get user input for CAPTCHA handling
        
    Returns:
        Updated job listings
    """
    if not job_listings:
        return job_listings
    
    total_jobs = len(job_listings)
    logger.info(f"Batch scraping {total_jobs} job descriptions")
    
    success_count = 0
    consecutive_failures = 0
    first_failed_index = None
    captcha_threshold = config.captcha_detection_threshold
    
    for i, job in enumerate(job_listings):
        if not job.job_url:
            logger.warning(f"Job {i+1}/{total_jobs} has no URL, skipping")
            continue
            
        url = job.job_url
        
        # Normalize URL if needed
        job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', url)
        if job_id_match:
            job_id = job_id_match.group(1)
            normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
            job.job_url = normalized_url
            url = normalized_url
            job.job_id = job_id
        
        logger.info(f"Processing job {i+1}/{total_jobs}: {job.title}")
        
        description, posted_date, job_details = scrape_job_description(
            driver, url, need_job_details=True
        )
        
        # Check if we got redirected to a job page with a job ID (for ad URLs)
        if not job_id_match and "pagead" in url:
            current_url = driver.current_url
            job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', current_url)
            if job_id_match:
                job_id = job_id_match.group(1)
                normalized_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                job.job_url = normalized_url
                job.job_id = job_id
                logger.info(f"Updated URL to simplified URL: {normalized_url}")
            
        # Update the JobListing object
        if description:
            job.description = description
            success_count += 1
            logger.info(f"✓ Got description for {job.title}")
            consecutive_failures = 0
        else:
            logger.info(f"✗ No description found for {job.title}")
            consecutive_failures += 1
            if consecutive_failures == 1:
                first_failed_index = i
            
            if consecutive_failures >= captcha_threshold:
                logger.warning(f"Detected {consecutive_failures} consecutive failures - possible CAPTCHA")
                
                if handle_possible_captcha(driver, input_prompt):
                    # Reset to the first failed job and try again
                    if first_failed_index is not None:
                        # Recursively process remaining jobs
                        remaining = job_listings[first_failed_index:]
                        processed = batch_scrape_descriptions(driver, remaining, input_prompt)
                        job_listings[first_failed_index:] = processed
                        break
                else:
                    logger.info("User requested exit during CAPTCHA handling")
                    break
            
        # Update other fields if available
        if posted_date:
            job.date_posted = posted_date
            
        if job_details:
            if job_details.get('job_type'):
                job.job_type = job_details['job_type']
                
            if job_details.get('work_setting'):
                job.work_setting = job_details['work_setting']
        
        if i < total_jobs - 1:
            random_delay(1.5, 3.0)
    
    logger.info(f"Successfully scraped {success_count}/{total_jobs} job descriptions")
    return job_listings 