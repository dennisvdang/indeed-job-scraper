#!/usr/bin/env python3
"""Browser setup and navigation helpers for Indeed job scraper."""

import random
import time
import os
import sys
from typing import Optional, Callable, Generator, Any
from contextlib import contextmanager, suppress
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException, WebDriverException
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

from .config import config
from .logger import logger

# Patch to suppress the "OSError: [WinError 6] The handle is invalid" error
# This happens during Chrome driver cleanup
original_stderr = sys.stderr

class SuppressSpecificErrors:
    def __enter__(self):
        sys.stderr = self
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = original_stderr
        
    def write(self, message):
        if "OSError: [WinError 6] The handle is invalid" not in message:
            original_stderr.write(message)
            
    def flush(self):
        original_stderr.flush()

class CaptchaDetectedException(Exception):
    """Exception raised when a CAPTCHA is detected."""
    pass

@contextmanager
def setup_browser(headless: bool = False) -> Generator[uc.Chrome, None, None]:
    """
    Set up and tear down browser instance.
    
    Args:
        headless: Whether to run in headless mode
        
    Yields:
        WebDriver instance
    """
    driver = None
    try:
        logger.info("Setting up browser...")
        options = uc.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.headless = headless
        
        driver = uc.Chrome(options=options, version_main=135)
        driver.maximize_window()
        logger.info("Browser setup complete")
        yield driver
    except WebDriverException as e:
        logger.error(f"Browser setup failed: {e}")
        try:
            # Fallback with minimal options
            minimal_options = uc.ChromeOptions()
            minimal_options.headless = headless
            driver = uc.Chrome(options=minimal_options)
            driver.maximize_window()
            logger.info("Browser setup complete with minimal options")
            yield driver
        except Exception as e:
            logger.error(f"Browser setup failed with minimal options: {e}")
            raise
    finally:
        if driver:
            logger.info("Closing browser")
            with SuppressSpecificErrors():
                driver.quit()

def random_delay(min_seconds: Optional[float] = None, max_seconds: Optional[float] = None) -> None:
    """
    Add a random delay to mimic human behavior.
    
    Args:
        min_seconds: Minimum seconds to delay (default from config)
        max_seconds: Maximum seconds to delay (default from config)
    """
    min_s = min_seconds if min_seconds is not None else config.min_delay_seconds
    max_s = max_seconds if max_seconds is not None else config.max_delay_seconds
    time.sleep(random.uniform(min_s, max_s))

def scroll_page(driver: uc.Chrome) -> None:
    """
    Scroll the page to load all content.
    
    Args:
        driver: WebDriver instance
    """
    logger.info("Scrolling page...")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for i in range(1, 11):
        driver.execute_script(f"window.scrollTo(0, {i * last_height / 10});")
        time.sleep(0.2)
    
    time.sleep(1)
    
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height > last_height:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

def navigate_to_next_page(driver: uc.Chrome) -> bool:
    """
    Navigate to the next page of search results.
    
    Args:
        driver: WebDriver instance
        
    Returns:
        bool: True if navigated to next page, False if no next page
    """
    try:
        next_buttons = driver.find_elements(By.CSS_SELECTOR, config.next_page_selector)
        if not next_buttons:
            logger.info("No next page button found - reached the last page")
            return False
        
        next_page_url = next_buttons[0].get_attribute('href')
        if not next_page_url:
            return False
            
        current_url = driver.current_url
        driver.get(next_page_url)
        
        WebDriverWait(driver, config.browser_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, config.job_card_selector))
        )
        
        if driver.current_url == current_url:
            return False
            
        random_delay()
        return True
        
    except (TimeoutException, NoSuchElementException, ElementNotInteractableException) as e:
        logger.warning(f"Error navigating to next page: {e}")
        return False

def handle_possible_captcha(driver: uc.Chrome, input_prompt: Callable = input) -> bool:
    """
    Handle a potential captcha situation by prompting the user.
    
    Args:
        driver: WebDriver instance
        input_prompt: Function to get user input
        
    Returns:
        bool: True if user confirmed captcha was solved, False if exit requested
    """
    captcha_message = """
    !! CAPTCHA DETECTED !!
    ======================
    
    Multiple job descriptions could not be retrieved.
    This usually happens when Indeed is showing a CAPTCHA verification.
    
    Please check the browser window and solve any CAPTCHAs if present.
    After solving the CAPTCHA, press Enter to continue scraping...
    """
    
    logger.warning(captcha_message)
    
    try:
        current_url = driver.current_url
        driver.get("https://www.indeed.com/")
        time.sleep(1)
    except Exception as e:
        logger.error(f"Error navigating to Indeed homepage: {e}")
    
    try:
        response = input_prompt("Press Enter after solving the CAPTCHA (or Ctrl+C to exit): ")
        time.sleep(2)
        
        try:
            if driver.current_url != current_url:
                driver.get(current_url)
                time.sleep(2)
        except Exception as e:
            logger.error(f"Error navigating back to original URL: {e}")
        
        return True
    except (KeyboardInterrupt, EOFError):
        logger.info("User requested exit")
        return False 