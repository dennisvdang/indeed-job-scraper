"""
Indeed Job Scraper Module

This module provides functions for scraping job listings from Indeed.com.
It includes functions for setting up a Selenium webdriver, navigating to job search results,
and extracting job details from Indeed pages.
"""

import time
import random
import re
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException


def setup_selenium_driver(headless: bool = True) -> webdriver.Chrome:
    """Set up and configure a Selenium Chrome driver for web scraping.
    
    Args:
        headless: Whether to run Chrome in headless mode
    
    Returns:
        webdriver.Chrome: Configured Chrome webdriver instance
    """
    # Set up Chrome options
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")  # Run in headless mode
    
    chrome_options.add_argument("--disable-gpu")  # Disable GPU hardware acceleration
    chrome_options.add_argument("--window-size=1920,1080")  # Set window size
    
    # Docker-specific options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set a realistic user agent
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    chrome_options.add_argument(f'user-agent={user_agent}')
    
    # Create and return the driver
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """Introduce a random delay between operations to avoid overwhelming the server.
    
    Args:
        min_seconds: Minimum delay time in seconds
        max_seconds: Maximum delay time in seconds
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def construct_search_url(job_title: str, location: str = "", search_radius: Optional[int] = None,
                         days_ago: int = 7, remote: bool = True) -> str:
    """Construct an Indeed search URL based on search parameters.
    
    Args:
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: Search radius in miles (default: 25 if location provided, None otherwise)
        days_ago: Number of days since job posting
        remote: Whether to search for remote jobs only
        
    Returns:
        str: A properly formatted Indeed search URL
    """
    # URL encode the job title (replace spaces with +)
    job_title_encoded = job_title.replace(' ', '+')
    
    # Construct the base URL
    base_url = f"https://www.indeed.com/jobs?q={job_title_encoded}"
    
    # Add location if provided
    if location:
        location_encoded = location.replace(' ', '+')
        base_url += f"&l={location_encoded}"
        
        # Add search radius if location is provided
        if search_radius is None:
            search_radius = 25  # Default to 25 miles if location provided
        base_url += f"&radius={search_radius}"
    
    # Add days ago filter
    if days_ago > 0:
        base_url += f"&fromage={days_ago}"
    
    # Add remote filter
    if remote:
        base_url += "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"
    
    return base_url


def extract_job_cards(driver: webdriver.Chrome) -> List[Dict[str, Any]]:
    """Extract job information from Indeed's job cards on the search results page.
    
    Args:
        driver: Selenium Chrome driver instance on the Indeed search results page
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing job information
    """
    # Wait for job cards to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.jobsearch-ResultsList > li"))
        )
    except TimeoutException:
        print("Timed out waiting for job cards to load")
        return []
    
    # Get all job cards
    job_cards = driver.find_elements(By.CSS_SELECTOR, "ul.jobsearch-ResultsList > li")
    
    # Initialize empty list to store job data
    jobs_data = []
    
    # Loop through each job card and extract data
    for card in job_cards:
        try:
            # Skip non-job elements (like ads)
            if not card.get_attribute("data-resultid"):
                continue
                
            # Extract job title
            title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
            title = title_element.get_attribute("title") if title_element else "Unknown"
            
            # Extract company name
            company_element = card.find_element(By.CSS_SELECTOR, "span.companyName")
            company = company_element.text if company_element else "Unknown"
            
            # Extract location
            location_element = card.find_element(By.CSS_SELECTOR, "div.companyLocation")
            location = location_element.text if location_element else "Unknown"
            
            # Extract salary if available
            try:
                salary_element = card.find_element(By.CSS_SELECTOR, "div.salary-snippet-container")
                salary = salary_element.text
            except NoSuchElementException:
                salary = "Not listed"
                
            # Extract job URL
            job_link_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
            job_url = job_link_element.get_attribute("href") if job_link_element else None
            
            # Extract job ID from URL
            job_id = None
            if job_url:
                job_id_match = re.search(r'jk=([a-zA-Z0-9]+)', job_url)
                job_id = job_id_match.group(1) if job_id_match else None
                
            # Add job data to list
            jobs_data.append({
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "job_url": job_url,
                "job_id": job_id,
                "source": "Indeed"
            })
                
        except NoSuchElementException:
            # Skip job cards that don't have expected elements
            continue
            
    return jobs_data


def scrape_job_details(driver: webdriver.Chrome, job_url: str) -> Dict[str, Any]:
    """Scrape detailed job information from a specific job page.
    
    Args:
        driver: Selenium Chrome driver instance
        job_url: URL of the job details page
        
    Returns:
        Dict[str, Any]: Dictionary containing detailed job information
    """
    # Navigate to job page
    driver.get(job_url)
    random_delay(3.0, 6.0)  # Longer delay for job details page
    
    # Initialize job details dictionary
    job_details = {}
    
    try:
        # Wait for job description to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#jobDescriptionText"))
        )
        
        # Extract job description
        job_description = driver.find_element(By.CSS_SELECTOR, "div#jobDescriptionText").text
        job_details["description"] = job_description
        
        # Try to extract additional details if available
        try:
            # Job type
            job_type_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Job type:')]/following-sibling::div")
            job_details["job_type"] = job_type_elements[0].text if job_type_elements else "Not specified"
            
            # Work schedule
            schedule_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Schedule:')]/following-sibling::div")
            job_details["schedule"] = schedule_elements[0].text if schedule_elements else "Not specified"
            
            # Salary
            salary_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Salary:')]/following-sibling::div")
            job_details["salary_detail"] = salary_elements[0].text if salary_elements else "Not specified"
            
        except NoSuchElementException:
            # Some details might not be available
            pass
            
    except (NoSuchElementException, TimeoutException) as e:
        print(f"Error scraping job details: {e}")
        job_details["description"] = "Failed to extract job description"
        
    return job_details


def scrape_indeed_jobs(job_title: str, location: str = "", search_radius: Optional[int] = None,
                      max_pages: int = 3, days_ago: int = 7, remote: bool = True, 
                      headless: bool = True) -> pd.DataFrame:
    """Main function to scrape Indeed jobs based on search criteria.
    
    Args:
        job_title: The job title to search for
        location: The location to search in (optional)
        search_radius: Search radius in miles (default: 25 if location provided, None otherwise)
        max_pages: Maximum number of search result pages to scrape
        days_ago: Number of days since job posting
        remote: Whether to search for remote jobs only
        headless: Whether to run Chrome in headless mode
        
    Returns:
        pd.DataFrame: DataFrame containing all scraped job information
    """
    # Set up the driver
    driver = setup_selenium_driver(headless=headless)
    
    try:
        # Construct the search URL
        search_url = construct_search_url(job_title, location, search_radius, days_ago, remote)
        print(f"Searching: {search_url}\n")
        
        # Initialize empty list to store all jobs
        all_jobs = []
        
        # Initialize set to track duplicate job IDs
        job_ids = set()
        
        # Iterate through pages
        for page in range(1, max_pages + 1):
            # Construct page URL
            page_url = search_url if page == 1 else f"{search_url}&start={(page-1)*10}"
            
            # Navigate to the page
            driver.get(page_url)
            random_delay()
            
            # Print status
            print(f"Scraping page {page}...")
            
            # Extract job cards
            jobs_on_page = extract_job_cards(driver)
            
            # Print number of job cards found
            print(f"Found {len(jobs_on_page)} job cards on the page")
            
            # Process each job
            for job in jobs_on_page:
                # Skip if we've already seen this job ID
                if job["job_id"] in job_ids:
                    continue
                    
                # Add to our set of seen job IDs
                job_ids.add(job["job_id"])
                
                # Print job being scraped
                print(f"Scraped: {job['title']} at {job['company']}")
                
                # Add to our list of all jobs
                all_jobs.append(job)
                
            # Print status after each page
            print(f"Total unique jobs: {len(all_jobs)} (removed {len(jobs_on_page) - (len(all_jobs) - len(job_ids) + len(jobs_on_page))} duplicates)\n")
            
            # Pause between pages
            random_delay(5.0, 8.0)
            
        # Create DataFrame from our list of jobs
        jobs_df = pd.DataFrame(all_jobs)
        
        # Optionally scrape detailed job descriptions
        # Note: This is commented out as it would significantly increase scraping time
        # and might trigger rate limiting from Indeed
        """
        print("\nScraping detailed job descriptions...")
        job_details = []
        for idx, job in jobs_df.iterrows():
            print(f"Scraping details for job {idx+1}/{len(jobs_df)}: {job['title']}")
            details = scrape_job_details(driver, job['job_url'])
            job_details.append(details)
            random_delay(8.0, 12.0)  # Longer delay for job details
            
        # Combine job details with main dataframe
        details_df = pd.DataFrame(job_details)
        jobs_df = pd.concat([jobs_df, details_df], axis=1)
        """
            
        return jobs_df
        
    finally:
        # Always close the driver
        driver.quit()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape jobs from Indeed.com')
    parser.add_argument('--job-title', type=str, required=True, help='Job title to search for')
    parser.add_argument('--location', type=str, default=None, help='Location to search in')
    parser.add_argument('--search-radius', type=int, default=None, help='Search radius in miles (default: 25 if location provided)')
    parser.add_argument('--max-pages', type=int, default=3, help='Maximum number of pages to scrape')
    parser.add_argument('--days-ago', type=int, default=7, help='Filter for jobs posted within this many days')
    parser.add_argument('--remote', action='store_true', default=True, help='Search for remote jobs only')
    parser.add_argument('--no-remote', action='store_false', dest='remote', help='Include non-remote jobs')
    parser.add_argument('--headless', action='store_true', default=True, help='Run Chrome in headless mode')
    parser.add_argument('--no-headless', action='store_false', dest='headless', help='Run Chrome in visible mode')
    
    args = parser.parse_args()
    
    jobs = scrape_indeed_jobs(
        job_title=args.job_title,
        location=args.location,
        search_radius=args.search_radius,
        max_pages=args.max_pages,
        days_ago=args.days_ago,
        remote=args.remote,
        headless=args.headless
    )
    
    # Save to CSV
    output_file = f"indeed_{args.job_title.replace(' ', '_').lower()}_jobs.csv"
    jobs.to_csv(output_file, index=False)
    print(f"Saved {len(jobs)} jobs to {output_file}.")