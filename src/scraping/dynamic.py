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
        options = ChromiumOptions()
        #options.set_argument('--headless') 
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
                soup = BeautifulSoup(self.driver.html, 'lxml')
                
                if cleanup_after:
                    self.cleanup()
                    
                return soup
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
                # Clear reference to driver
                self.driver = None
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
            # Special handling for Google consent pages
            current_url = self.driver.url
            self.logger.info(f"Checking for cookie consent on: {current_url}")
            
            # Google consent specific check
            if 'consent.google.com' in current_url:
                self.logger.info("Detected Google consent page, using special handling")

                for selector in [
                    'button[aria-label="Accept all"]',
                    'button:contains("Accept all")',
                    'form[action*="consent.google.com"] button',
                    '//div[contains(@class,"tB5Jxf-")]//button',
                    '//button[contains(., "Accept all")]',
                    '//button[contains(translate(., "ACEPT L", "acept l"), "accept all")]'
                ]:
                    try:
                        # CSS selector first
                        if not selector.startswith('//'):
                            elements = self.driver.eles(selector)
                        else:
                            # XPath if selector starts with //
                            elements = self.driver.eles(selector, mode='xpath')
                        
                        if elements:
                            for element in elements[:3]:  # Only try first 3 matches
                                try:
                                    element.click()
                                    self.logger.info(f"Clicked Google consent button using selector: {selector}")
                                    time.sleep(1.5)  # Longer wait for Google consent
                                    return True
                                except Exception as e:
                                    self.logger.debug(f"Failed to click element with selector {selector}: {str(e)}")
                                    continue
                    except Exception as e:
                        self.logger.debug(f"Error finding elements with selector '{selector}': {str(e)}")
                        continue
                
                # try Js click on any potential consent button
                try:
                    result = self.driver.run_js('''
                        const buttons = document.querySelectorAll('button');
                        for (const button of buttons) {
                            if (button.innerText.toLowerCase().includes('accept') || 
                                button.innerText.toLowerCase().includes('agree') ||
                                button.innerText.toLowerCase().includes('consent')) {
                                button.click();
                                return true;
                            }
                        }
                        return false;
                    ''')
                    if result:
                        self.logger.info("Clicked consent button using JavaScript")
                        time.sleep(1.5)
                        return True
                except Exception as e:
                    self.logger.debug(f"Error clicking with JavaScript: {str(e)}")
            
            # Generic consent handling 
            common_texts = ['accept all', 'i accept', 'accept cookies', 'agree', 'got it', 'ok', 'allow']
            
            for text in common_texts:
                try:
                    # Find any clickable element containing this text
                    elements = self.driver.eles(f'button:contains("{text}")')
                    
                    if elements:
                        for element in elements[:3]:  # Only try first 3 matches
                            try:
                                element.click()
                                self.logger.info(f"Clicked cookie consent with text: {text}")
                                time.sleep(0.5) 
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