from typing import Optional, Dict
from urllib.parse import urlparse
import time
import re
import json

from DrissionPage import ChromiumPage, ChromiumOptions
from bs4 import BeautifulSoup
from .base import BaseScraper
from src.processing.content_extractor import ContentExtractor
from src.processing.metadata_extractor import MetadataExtractor
from src.utils.text_utils import extract_domain, clean_title_from_headline

class DynamicScraper(BaseScraper):
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)

        # Initialise cookie consent handler
        self._cookie_handler = None

        # Optimise Chrome options for speed and stability
        options = ChromiumOptions()
        options.set_argument('--headless') 
        options.set_argument('--disable-dev-shm-usage')
        options.set_argument('--disable-software-rasterizer')
        options.set_argument('--disable-extensions')
        options.set_argument('--disable-features=site-per-process')
        options.set_argument('--disable-gpu') 

        # Add performance options
        options.set_argument('--blink-settings=imagesEnabled=false') 
        options.set_argument('--disable-remote-fonts')  
        options.set_argument('--disable-sync') 
        options.set_argument('--disable-plugins')  
        options.set_argument('--disable-plugins-discovery')  
        options.set_argument('--disable-bundled-ppapi-flash')  
        options.set_argument('--disable-component-extensions-with-background-pages')  
        options.set_argument('--disable-default-apps')  
        options.set_argument('--disable-background-networking')  
        options.set_argument('--disable-background-timer-throttling')  
        options.set_argument('--disable-backgrounding-occluded-windows')  
        options.set_argument('--disable-breakpad')  
        options.set_argument('--disable-client-side-phishing-detection')  
        options.set_argument('--disable-infobars')  
        options.set_argument('--disable-notifications')  
        options.set_argument('--disable-popup-blocking')  
        options.set_argument('--disable-prompt-on-repost')  
        options.set_argument('--no-first-run')  
        options.set_argument('--no-default-browser-check')  
        options.set_argument('--no-pings')  
        options.set_argument('--disable-ipc-flooding-protection')  
        options.set_argument('--disable-hang-monitor')  
        options.set_argument('--disable-features=IsolateOrigins')  
        options.set_argument('--window-size=400,400') 

        # Lazy loading for images and iframes
        options.set_argument('--enable-features=LazyFrameLoading,LazyImageLoading')
        options.set_argument('--force-lazy-image-loading')  
        options.set_argument('--enable-lazy-image-loading')  
        options.set_argument('--enable-lazy-frame-loading')  

        # Set timeouts directly through ChromiumOptions
        options.page_load_timeout = 25
        options.script_timeout = 15
        options.set_timeouts(15, 25, 25)  # implicitly_wait, page_load, script
        options.page_load_strategy = 'eager' 

        self.driver = ChromiumPage(options)
        self.driver.set.timeouts(15, 25, 25)  # implicitly_wait, page_load, script

        self.max_retries = 2  # Number of retries
        self.retry_delay = 1.0  # Delay between retries
        self.page_load_timeout = 25  # Timeout for page load

        
    def get_page_content(self, url) -> Optional[BeautifulSoup]:
        """
        Fetch page content with dynamic loading support.
        
        Args:
            url: URL to scrape
            
        Returns:
            BeautifulSoup object or None if failed
        """
        if not url:
            return None
        
        start_time = time.time()
        
        try:
            # Navigate to the URL with a longer timeout
            self.driver.get(url, timeout=self.page_load_timeout + 5)
            
            # Sleep for a second
            time.sleep(1)
        
            self.logger.info(f"Successfully loaded page in {time.time() - start_time:.2f}s")
            return BeautifulSoup(self.driver.html, 'lxml')
          
        except Exception as e:
            self.logger.warning(f"Error loading page: {str(e)}")
            # Return whatever HTML we have
            try:
                return BeautifulSoup(self.driver.html, 'lxml')
            except:
                return BeautifulSoup("", 'lxml')

    def _cleanup_browser(self):
        """Clean up browser resources"""
        try:
            # Quit the driver
            try:
                self.driver.quit()
            except:
                pass
        except Exception as e:
            self.logger.warning(f"Error cleaning up browser: {str(e)}")

    def get_page_soup(self) -> BeautifulSoup:
        """Get BeautifulSoup object of the current page"""
        try:
            # DrissionPage has a built-in property to get page HTML
            html = self.driver.html
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            return soup
        except Exception as e:
            self.logger.error(f"Error getting page soup: {str(e)}")
            return BeautifulSoup("", 'html.parser')  # Return empty soup on error

    def __del__(self):
        """Clean up resources when the object is garbage collected"""
        try:
            self._cleanup_browser()
        except:
            pass

    def go_to_url(self, url: str, timeout: int = 15) -> bool:
        """Navigate to a URL
        
        Args:
            url: The URL to navigate to
            timeout: Timeout in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info(f"Navigating to URL: {url}")
        
        try:
            self.driver.get(url, timeout=timeout)
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to {url}: {str(e)}")
            return False

    def check_for_cookie_consent(self) -> bool:
        """Check for cookie consent banners and attempt to accept them
        
        Returns:
            True if cookie consent was handled, False otherwise
        """
        try:
            common_texts = ['accept all', 'i accept', 'accept cookies', 'agree', 'got it', 'ok', 'allow']
            
            # Try to find buttons with these texts
            for text in common_texts:
                try:
                    # Find any clickable element containing this text
                    elements = self.driver.eles(f'button:contains("{text}")')
                    
                    if elements:
                        for element in elements[:3]:  # Only try the first 3 matches
                            try:
                                element.click()
                                self.logger.info(f"Clicked cookie consent with text: {text}")
                                time.sleep(0.5)  # Short wait after clicking
                                return True
                            except:
                                continue
                except Exception as e:
                    self.logger.debug(f"Error finding elements with text '{text}': {str(e)}")
                    continue
            
            return False
        except Exception as e:
            self.logger.error(f"Error handling cookie consent: {str(e)}")
            return False