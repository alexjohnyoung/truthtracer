from abc import ABC, abstractmethod
from typing import Optional, Dict
from bs4 import BeautifulSoup
import requests
import logging
from src.processing.content_extractor import ContentExtractor
from src.processing.metadata_extractor import MetadataExtractor
from src.utils.text_utils import extract_domain, clean_title_from_headline

class BaseScraper(ABC):
    """Abstract base class for all scrapers"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.logger = logging.getLogger(__name__)
        self.logger.propagate = False
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        # Initialise content and metadata extractors
        self.content_extractor = ContentExtractor()
        self.metadata_extractor = MetadataExtractor()

    @abstractmethod
    def get_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse webpage content"""
        pass

    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        Extract structured data from parsed content

        Args:
            soup: BeautifulSoup object of the parsed page
            url: URL of the page being scraped

        Returns:
            Dict containing extracted content
        """
        domain = extract_domain(url)
        
        try:
            # Use the ContentExtractor for text extraction
            content_dict = self.content_extractor.extract_content(soup, url)
            
            # Use the MetadataExtractor for metadata
            metadata_dict = self.metadata_extractor.extract_metadata(soup, url)
            
            # Merge the dictionaries (prioritise metadata_dict for overlapping keys)
            result = {**content_dict, **metadata_dict}
            
            # If headline is still empty, try the title tag as last resort
            if not result.get('headline') or len(result.get('headline', '')) < 5:
                title = soup.find('title')
                if title:
                    title_text = title.text.strip()
                    result['headline'] = clean_title_from_headline(title_text)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting content: {str(e)}")
            return {
                'url': url,
                'domain': domain,
                'headline': '',
                'author': None,
                'publishDate': None,
                'text': '',
                'links': []
            }