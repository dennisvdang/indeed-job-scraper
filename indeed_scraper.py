"""
Indeed Job Scraper Module

A tool for scraping job listings from Indeed.com, with support for filtering by location,
work arrangement, and other criteria. Results are saved to CSV for further analysis.
"""

import time
import random
import re
import signal
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd


# Global variable to track if the script should exit
should_exit = False


def signal_handler(signum, frame):
    """Handle exit signals gracefully."""
    global should_exit
    print("\n\nReceived exit signal. Cleaning up...")
    should_exit = True


# Register the signal handler for Ctrl+C (SIGINT)
signal.signal(signal.SIGINT, signal_handler)


@dataclass
class JobListing:
    """Data class to store job listing information."""
    title: str
    company: str
    location: str
    salary: str
    job_url: Optional[str]
    job_id: Optional[str]
    source: str = "Indeed"


def setup_selenium_driver(headless: bool = True) -> webdriver.Chrome:
    """Configure and return a Selenium Chrome driver for web scraping."""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Essential Chrome options
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(options=chrome_options)


def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """Add a random delay between operations to avoid overwhelming the server."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def construct_search_url(job_title: str, location: str = "", search_radius: Optional[int] = None,
                        days_ago: int = 7, work_arrangement: str = "any") -> str:
    """Build an Indeed search URL with the specified parameters."""
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


def extract_job_cards(driver: webdriver.Chrome) -> List[JobListing]:
    """Extract job information from Indeed's job cards on the search results page."""
    global should_exit
    
    try:
        # Wait for job cards to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.jobsearch-ResultsList > li"))
        )
    except TimeoutException:
        print("Timed out waiting for job cards to load")
        return []
    
    jobs_data = []
    job_cards = driver.find_elements(By.CSS_SELECTOR, "ul.jobsearch-ResultsList > li")
    
    for card in job_cards:
        # Check if exit signal received
        if should_exit:
            print("Stopping job card extraction...")
            break
            
        try:
            # Skip non-job elements
            if not card.get_attribute("data-resultid"):
                continue
            
            # Extract job details
            title = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]").get_attribute("title")
            company = card.find_element(By.CSS_SELECTOR, "span.companyName").text
            location = card.find_element(By.CSS_SELECTOR, "div.companyLocation").text
            
            # Extract salary if available
            try:
                salary = card.find_element(By.CSS_SELECTOR, "div.salary-snippet-container").text
            except NoSuchElementException:
                salary = "Not listed"
            
            # Extract job URL and ID
            job_link = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
            job_url = job_link.get_attribute("href")
            job_id = re.search(r'jk=([a-zA-Z0-9]+)', job_url).group(1) if job_url else None
            
            jobs_data.append(JobListing(
                title=title or "Unknown",
                company=company or "Unknown",
                location=location or "Unknown",
                salary=salary,
                job_url=job_url,
                job_id=job_id
            ))
                
        except NoSuchElementException:
            continue
            
    return jobs_data


def scrape_indeed_jobs(job_title: str, location: str = "", search_radius: Optional[int] = None,
                      max_pages: int = 3, days_ago: int = 7, work_arrangement: str = "any", 
                      headless: bool = True) -> pd.DataFrame:
    """Main function to scrape Indeed jobs based on search criteria."""
    global should_exit
    driver = None
    
    try:
        driver = setup_selenium_driver(headless=headless)
        search_url = construct_search_url(job_title, location, search_radius, days_ago, work_arrangement)
        print(f"Searching: {search_url}\n")
        print("Press Ctrl+C at any time to stop the scraper safely.\n")
        
        all_jobs = []
        job_ids = set()
        
        for page in range(1, max_pages + 1):
            # Check if exit signal received
            if should_exit:
                print("Stopping scraper...")
                break
            
            page_url = search_url if page == 1 else f"{search_url}&start={(page-1)*10}"
            driver.get(page_url)
            random_delay()
            
            print(f"Scraping page {page}...")
            jobs_on_page = extract_job_cards(driver)
            print(f"Found {len(jobs_on_page)} job cards on the page")
            
            # Process unique jobs
            for job in jobs_on_page:
                if job.job_id and job.job_id not in job_ids:
                    job_ids.add(job.job_id)
                    print(f"Scraped: {job.title} at {job.company}")
                    all_jobs.append(job.__dict__)
            
            print(f"Total unique jobs: {len(all_jobs)}\n")
            random_delay(5.0, 8.0)
        
        return pd.DataFrame(all_jobs)
        
    finally:
        if driver:
            driver.quit()
            print("\nCleaned up browser resources.")


if __name__ == "__main__":
    import argparse
    from argparse import BooleanOptionalAction
    
    parser = argparse.ArgumentParser(description='Scrape jobs from Indeed.com')
    parser.add_argument('--job-title', type=str, required=True, help='Job title to search for')
    parser.add_argument('--location', type=str, default=None, help='Location to search in')
    parser.add_argument('--search-radius', type=int, default=None, help='Search radius in miles (default: 25 if location provided)')
    parser.add_argument('--max-pages', type=int, default=3, help='Maximum number of pages to scrape')
    parser.add_argument('--days-ago', type=int, default=7, help='Filter for jobs posted within this many days')
    parser.add_argument('--work-arrangement', type=str, choices=['remote', 'hybrid', 'any'], default='any', 
                       help='Work arrangement preference (remote, hybrid, or any)')
    parser.add_argument('--headless', type=bool, default=True, action=BooleanOptionalAction, 
                       help='Run Chrome in headless mode (without GUI)')
    
    args = parser.parse_args()
    
    try:
        jobs = scrape_indeed_jobs(
            job_title=args.job_title,
            location=args.location,
            search_radius=args.search_radius,
            max_pages=args.max_pages,
            days_ago=args.days_ago,
            work_arrangement=args.work_arrangement,
            headless=args.headless
        )
        
        output_file = f"indeed_{args.job_title.replace(' ', '_').lower()}_jobs.csv"
        jobs.to_csv(output_file, index=False)
        print(f"\nSaved {len(jobs)} jobs to {output_file}.")
        
    except KeyboardInterrupt:
        print("\nScript terminated by user. Any scraped data will be saved.")
        sys.exit(0)