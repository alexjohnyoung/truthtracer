from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
import re
from .base import BaseScraper
from typing import Dict
import json
from src.processing.content_extractor import ContentExtractor
from src.processing.metadata_extractor import MetadataExtractor
from src.utils.text_utils import extract_domain, clean_title_from_headline

class StaticScraper(BaseScraper):
    """Static content scraper implementation with JavaScript detection"""

    def __init__(self, timeout: int = 30):
        """Initialise with content and metadata extractors"""
        super().__init__(timeout)

    @staticmethod
    def requires_javascript(soup: BeautifulSoup, raw_html: str) -> bool:
        """
        Check if the page requires JavaScript for content rendering

        Indicators of JavaScript dependency:
        1. Empty content containers
        2. Presence of app mounting points
        3. Dynamic content loading patterns
        4. Noscript warnings
        
        Args:
            soup: BeautifulSoup object of the page
            raw_html: Raw HTML text of the page
            
        Returns:
            bool: True if the page appears to require JavaScript
        """
        # Check for common JS framework root elements
        js_roots = soup.find_all(class_=re.compile(r'(app|root|main)-container|^(app|root|main)$'))
        if js_roots and all(len(root.get_text(strip=True)) < 50 for root in js_roots):
            return True

        # Check for SPA mounting points
        mount_points = ['#app', '#root', '#main', '[data-reactroot]', 'ng-app', 'ng-view', 'v-app']
        for point in mount_points:
            if soup.select(point):
                return True

        # Check for dynamic content loading patterns
        if re.search(r'window\.__INITIAL_STATE__|window\.__PRELOADED_STATE__', raw_html):
            return True

        # Look for noscript warnings
        noscript_elements = soup.find_all('noscript')
        for noscript in noscript_elements:
            text = noscript.get_text(strip=True).lower()
            if any(word in text for word in ['enable', 'required', 'javascript', 'please']):
                return True

        # Check for empty content containers with loading states
        content_containers = soup.find_all(class_=re.compile(r'content|main|article|post'))
        if content_containers:
            empty_containers = [
                container for container in content_containers
                if len(container.get_text(strip=True)) < 50 and
                   any(attr in str(container) for attr in ['loading', 'skeleton', 'placeholder'])
            ]
            if len(empty_containers) / len(content_containers) > 0.5:
                return True

        return False

    def get_page_content(self, url: str):
        """
        Fetch page content and determine if JavaScript is required

        Returns:
            Tuple[BeautifulSoup, bool]: (parsed content, requires_javascript)
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            requires_js = self.requires_javascript(soup, response.text)
            return soup, requires_js
        except requests.RequestException as e:
            self.logger.error(f"Error fetching {url}: {str(e)}")
            return None, False

    def extract_content(self, soup: BeautifulSoup, url: str):
        """
        Extract content from a webpage
        
        Args:
            soup: BeautifulSoup object for the page
            url: URL of the page
            
        Returns:
            dict: Content including metadata and text with JS detection
        """
        # Call the parent class implementation
        result = super().extract_content(soup, url)
        
        # Add JS detection specific to StaticScraper
        result['requires_javascript'] = self.requires_javascript(soup, str(soup) if soup else "")
        
        return result