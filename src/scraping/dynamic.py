from typing import Optional, Dict
from urllib.parse import urlparse
import time

from DrissionPage import ChromiumPage, ChromiumOptions
from bs4 import BeautifulSoup
from .base import BaseScraper

class DynamicScraper(BaseScraper):
    def __init__(self, timeout: int = 30):
        super().__init__(timeout)

        # Initialise cookie consent handler
        self._cookie_handler = None

        # Optimise Chrome options for speed and stability
        self.options = ChromiumOptions()
        #self.options.set_argument('--headless') 
        self.options.set_argument('--disable-dev-shm-usage')
        self.options.set_argument('--disable-software-rasterizer')
        self.options.set_argument('--disable-extensions')
        self.options.set_argument('--disable-features=site-per-process')
        self.options.set_argument('--disable-gpu') 

        # Add performance options
        self.options.set_argument('--blink-settings=imagesEnabled=false') 
        self.options.set_argument('--disable-remote-fonts')  
        self.options.set_argument('--disable-sync') 
        self.options.set_argument('--disable-plugins')  
        self.options.set_argument('--disable-plugins-discovery')  
        self.options.set_argument('--disable-bundled-ppapi-flash')  
        self.options.set_argument('--disable-component-extensions-with-background-pages')  
        self.options.set_argument('--disable-default-apps')  
        self.options.set_argument('--disable-background-networking')  
        self.options.set_argument('--disable-background-timer-throttling')  
        self.options.set_argument('--disable-backgrounding-occluded-windows')  
        self.options.set_argument('--disable-breakpad')  
        self.options.set_argument('--disable-client-side-phishing-detection')  
        self.options.set_argument('--disable-infobars')  
        self.options.set_argument('--disable-notifications')  
        self.options.set_argument('--disable-popup-blocking')  
        self.options.set_argument('--disable-prompt-on-repost')  
        self.options.set_argument('--no-first-run')  
        self.options.set_argument('--no-default-browser-check')  
        self.options.set_argument('--no-pings')  
        self.options.set_argument('--disable-ipc-flooding-protection')  
        self.options.set_argument('--disable-hang-monitor')  
        self.options.set_argument('--disable-features=IsolateOrigins')  
        self.options.set_argument('--window-size=400,400') 

        # Lazy loading for images and iframes
        self.options.set_argument('--enable-features=LazyFrameLoading,LazyImageLoading')
        self.options.set_argument('--force-lazy-image-loading')  
        self.options.set_argument('--enable-lazy-image-loading')  
        self.options.set_argument('--enable-lazy-frame-loading')  

        # Set timeouts directly through ChromiumOptions
        self.options.page_load_timeout = 25
        self.options.script_timeout = 15
        self.options.set_timeouts(15, 25, 25)  # implicitly_wait, page_load, script
        self.options.page_load_strategy = 'eager' 
        
        self.driver = self._initialize_driver()
        
        self.max_retries = 2  # Number of retries
        self.retry_delay = 1.0  # Delay between retries
        self.page_load_timeout = 25  # Timeout for page load
        
    def _initialize_driver(self):
        """Initialize or reinitialize the ChromiumPage driver with current options"""
        try:
            driver = ChromiumPage(self.options)
            driver.set.timeouts(15, 25, 25)  # implicitly_wait, page_load, script
            self.logger.info("Successfully initialized ChromiumPage driver")
            return driver
        except Exception as e:
            self.logger.error(f"Failed to initialize driver: {str(e)}")
            return None

    def get_page_content(self, url, cleanup_after=False) -> Optional[BeautifulSoup]:
        """
        Fetch page content with dynamic loading support.
        
        Args:
            url: URL to scrape
            cleanup_after: If True, browser will be cleaned up after getting content
            
        Returns:
            BeautifulSoup object or None if failed
        """
        if not url:
            return None
        
        start_time = time.time()
        
        if self.driver is None:
            self.driver = self._initialize_driver()
            if self.driver is None:
                return None
        
        try:
            # Navigate to the URL with a longer timeout
            self.driver.get(url, timeout=self.page_load_timeout + 5)
            
            # Sleep for a second
            time.sleep(1)
        
            self.logger.info(f"Successfully loaded page in {time.time() - start_time:.2f}s")
            soup = BeautifulSoup(self.driver.html, 'lxml')
            
            if cleanup_after:
                self.cleanup()
                
            return soup
          
        except Exception as e:
            self.logger.warning(f"Error loading page: {str(e)}")
            # Return whatever HTML we have
            try:
                if self.driver is not None:
                    soup = BeautifulSoup(self.driver.html, 'lxml')
                    
                    if cleanup_after:
                        self.cleanup()
                        
                    return soup
                else:
                    self.logger.warning("Driver is None, cannot get HTML")
                    return BeautifulSoup("", 'lxml')
            except:
                return BeautifulSoup("", 'lxml')

    def cleanup(self):
        """Clean up browser resources"""
        try:
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.logger.info("Browser successfully quit")
                except Exception as e:
                    self.logger.warning(f"Error quitting driver: {str(e)}")
                finally:
                    # Always clear reference to driver, even if an error occurred
                    self.driver = None
        except Exception as e:
            self.logger.warning(f"Error cleaning up browser: {str(e)}")

    def get_page_soup(self) -> BeautifulSoup:
        """Get BeautifulSoup object of the current page"""
        try:
            # Check if driver is None and try to reinitialize it
            if self.driver is None:
                self.logger.warning("Driver is None, attempting to reinitialize in get_page_soup")
                self.driver = self._initialize_driver()
                if self.driver is None:
                    self.logger.error("Failed to reinitialize driver in get_page_soup")
                    return BeautifulSoup("", 'html.parser')
                
            # DrissionPage has a built-in property to get page HTML
            html = self.driver.html
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            return soup
        except Exception as e:
            self.logger.error(f"Error getting page soup: {str(e)}")
            return BeautifulSoup("", 'html.parser')

    def __del__(self):
        """Clean up resources when the object is garbage collected"""
        self.cleanup()

    def go_to_url(self, url: str, timeout: int = 15) -> bool:
        """Navigate to a URL
        
        Args:
            url: The URL to navigate to
            timeout: Timeout in seconds
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.info(f"Navigating to URL: {url}")
        
        # Check if driver is None and try to reinitialize it
        if self.driver is None:
            self.logger.warning("Driver is None, attempting to reinitialize")
            self.driver = self._initialize_driver()
            if self.driver is None:
                self.logger.error("Failed to reinitialize driver")
                return False
        
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
        return False 