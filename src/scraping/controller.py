"""
Scraping controller module for news article content retrieval.

This module orchestrates the scraping process, making intelligent decisions about
whether to use static or dynamic scraping approaches based on site characteristics,
content analysis, and predefined rules.
"""

import logging
import time
import traceback
from typing import Dict, Optional, Set, List

from src.utils.logging_utils import get_logger
from src.google.google import GoogleSearchScraper
from .pipeline import ScrapingPipeline


class ScrapingController:
    """
    Central controller for the scraping system that orchestrates the scraping process
    using the pipeline architecture.
    """
    
    def __init__(self):
        """Initialise the scraping controller"""
        # Use the pipeline architecture
        self.pipeline = ScrapingPipeline()
        
        # Configure logging using the centralized utility
        self.logger = get_logger(__name__)
        self.tag = "[Controller]"
        
        # Lazy initialisation
        self._google_scraper = None

    @property
    def google_scraper(self):
        """Lazy initialisation property for GoogleSearchScraper"""
        if self._google_scraper is None:
            self._google_scraper = GoogleSearchScraper()
        return self._google_scraper

    def log(self, message: str, level: str = 'info') -> None:
        """Log a message with the specified level"""
        log_message = f"{self.tag} {message}"
        if level == 'error':
            self.logger.error(log_message)
        elif level == 'warning':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    def scrape_content(self, url: str) -> Optional[Dict]:
        """
        Scrape content from a URL using the pipeline architecture
        
        Args:
            url: URL of the article to scrape
            
        Returns:
            Dictionary containing scraped content or None if scraping failed
        """
        self.log(f"Starting content scraping for URL: {url}")
        
        start_time = time.time()
        
        try:
            # Use the pipeline to handle the entire scraping process
            content = self.pipeline.scrape(url)
            
            if content:
                execution_time = time.time() - start_time
                text_length = len(content.get('text', ''))
                self.log(f"Successfully scraped content ({text_length} chars) in {execution_time:.2f} seconds")
                return content
            else:
                self.log(f"Failed to scrape content from {url}", level='warning')
                return None

        except Exception as e:
            self.log(f"Error during scraping: {str(e)}", level='error')
            self.log(f"Traceback: {traceback.format_exc()}", level='error')
            return None

    def search_for_articles(self, query: str, days_old: int = 7, num_results: int = 10, publish_date: str = None) -> List[Dict[str, str]]:
        """
        Search for news articles (delegates to ScrapingPipeline)
        
        Args:
            query: The search query
            days_old: How many days old the articles can be (default: 7)
            num_results: Maximum number of results to return
            publish_date: Publication date of the article being analysed (optional)
            
        Returns:
            List of dictionaries containing article information
        """
        self.log(f"Searching for articles with query: {query}, days_old: {days_old}")
        try:
            results = self.pipeline.search_for_articles(query, days_old=days_old, num_results=num_results, publish_date=publish_date)
            self.log(f"Found {len(results)} articles")
            return results
        except Exception as e:
            self.log(f"Error searching for articles: {str(e)}", level='error')
            return []

    def cleanup(self):
        """
        Clean up all resources used by the controller and its dependencies.
        
        This should be called when the controller is no longer needed or
        before application shutdown.
        """
        self.log("Cleaning up ScrapingController resources")
        
        # Clean up pipeline resources if available
        if hasattr(self, 'pipeline'):
            try:
                # Clean up pipeline dynamic scraper
                if hasattr(self.pipeline, 'dynamic_scraper'):
                    try:
                        self.pipeline.dynamic_scraper.cleanup()
                        self.log("Successfully cleaned up pipeline dynamic scraper")
                    except Exception as e:
                        self.log(f"Error cleaning up pipeline dynamic scraper: {str(e)}", level='error')
            except Exception as e:
                self.log(f"Error accessing pipeline resources: {str(e)}", level='error')
        
        # Clean up google scraper if initialised
        if hasattr(self, '_google_scraper') and self._google_scraper is not None:
            try:
                self._google_scraper.cleanup()
                self._google_scraper = None
                self.log("Successfully cleaned up GoogleSearchScraper")
            except Exception as e:
                self.log(f"Error cleaning up GoogleSearchScraper: {str(e)}", level='error')
        
        self.log("ScrapingController cleanup completed")
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            self.cleanup()
        except:
            pass