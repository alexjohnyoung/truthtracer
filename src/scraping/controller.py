import logging
import time
import traceback
import os
from typing import Dict, Optional, Set, List

from src.utils.logging_utils import get_logger
from src.google.google import GoogleSearchScraper
from .pipeline import ScrapingPipeline
from src.utils.status import update_status


class ScrapingController:
    """
    Central controller for the scraping system that orchestrates the scraping process
    using the pipeline architecture.
    """
    
    def __init__(self):
        """Initialise the scraping controller"""
        # Get configuration from environment variables
        self.scraping_timeout = int(os.environ.get('SCRAPING_TIMEOUT', 30))
        self.max_retries = int(os.environ.get('MAX_RETRIES', 3))
        
        self.pipeline = ScrapingPipeline(
            timeout=self.scraping_timeout,
            max_retries=self.max_retries
        )

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
        self.log(f"Using scraping_timeout={self.scraping_timeout}s, max_retries={self.max_retries}")
        
        start_time = time.time()
        
        try:
            # Update status at the beginning of scraping
            update_status(f"Fetching article from {url}", 6, "Web Scraping", 1)
            
            # Use the pipeline to handle the entire scraping process
            content = self.pipeline.scrape(url)
            
            if content:
                execution_time = time.time() - start_time
                text_length = len(content.get('text', ''))
                metadata_status = []
                metadata_methods = {}
                
                # Report on what metadata was successfully extracted
                if content.get('headline'):
                    metadata_status.append("headline")
                    if content.get('headline_source'):
                        metadata_methods['headline'] = content.get('headline_source')
                if content.get('author'):
                    metadata_status.append("author")
                    if content.get('author_source'):
                        metadata_methods['author'] = content.get('author_source')
                if content.get('publishDate'):
                    metadata_status.append("publish date")
                    if content.get('date_source'):
                        metadata_methods['publishDate'] = content.get('date_source')
                
                if metadata_status:
                    metadata_msg = f"Extracted {', '.join(metadata_status)}"
                    
                    # Add extraction method details if available
                    method_details = []
                    for field, method in metadata_methods.items():
                        if method:
                            method_details.append(f"{field} via {method}")
                    
                    if method_details:
                        metadata_msg += f" using {', '.join(method_details)}"
                        
                    update_status(metadata_msg, 9, "Metadata Extraction", 1)
                
                self.log(f"Successfully scraped content ({text_length} chars) in {execution_time:.2f} seconds")
                update_status(f"Successfully scraped {text_length} characters of content", 10, "Web Scraping", 1)
                return content
            else:
                self.log(f"Failed to scrape content from {url}", level='warning')
                update_status(f"Failed to scrape content from {url}", 10, "Error", -1)
                return None

        except Exception as e:
            self.log(f"Error during scraping: {str(e)}", level='error')
            self.log(f"Traceback: {traceback.format_exc()}", level='error')
            update_status(f"Error scraping content: {str(e)[:100]}", 10, "Error", -1)
            return None

    def search_for_articles(self, query: str, original_url: str = None, days_old: int = 7, num_results: int = 10, publish_date: str = None) -> List[Dict[str, str]]:
        """
        Search for news articles (delegates to ScrapingPipeline)
        
        Args:
            query: The search query
            original_url: URL to exclude from results (same domain will be filtered)
            days_old: How many days old the articles can be (default: 7)
            num_results: Maximum number of results to return
            publish_date: Publication date of the article being analysed (optional)
            
        Returns:
            List of dictionaries containing article information
        """
        from src.utils.status import update_status
        
        self.log(f"Searching for articles with query: {query}, days_old: {days_old}")
        update_status(f"Searching for related articles (max {num_results} results)", 41, "Reference Search", 3)
        
        if original_url:
            self.log(f"Will exclude results matching domain of original URL: {original_url}")
            
        try:
            update_status("Executing search query...", 42, "Reference Search", 3)
            
            results = self.pipeline.search_for_articles(
                query=query, 
                original_url=original_url,
                days_old=days_old, 
                num_results=num_results, 
                publish_date=publish_date
            )
            
            result_count = len(results)
            self.log(f"Found {result_count} articles")
            
            if result_count > 0:
                domains = set()
                for result in results:
                    if 'url' in result:
                        from src.utils.text_utils import extract_domain
                        domains.add(extract_domain(result['url']))
                
                domain_str = ", ".join(list(domains)[:3])
                if len(domains) > 3:
                    domain_str += f" and {len(domains)-3} more"
                
                update_status(f"Found {result_count} related articles from {domain_str}", 45, "Reference Search", 3)
            else:
                update_status("No related articles found", 45, "Reference Search", 3)
                
            return results
            
        except Exception as e:
            self.log(f"Error searching for articles: {str(e)}", level='error')
            update_status(f"Error searching for related articles: {str(e)[:100]}", 45, "Error", -1)
            return []

    def cleanup(self):
        """
        Clean up all resources used by the controller and its dependencies.
        """
        self.log("Cleaning up ScrapingController resources")
        
        try:
            if hasattr(self, 'pipeline') and self.pipeline is not None:
                self.pipeline.cleanup()
                self.log("Successfully cleaned up pipeline resources")
        except Exception as e:
            self.log(f"Error cleaning up pipeline: {str(e)}", level='error')
            
        try:
            if hasattr(self, '_google_scraper') and self._google_scraper is not None:
                if hasattr(self._google_scraper, 'cleanup'):
                    self._google_scraper.cleanup()
                    self.log("Successfully cleaned up GoogleSearchScraper")
                self._google_scraper = None
        except Exception as e:
            self.log(f"Error cleaning up GoogleSearchScraper: {str(e)}", level='error')
        
        self.log("ScrapingController cleanup completed")
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            self.cleanup()
        except Exception:
            pass