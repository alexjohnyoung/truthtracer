"""
Pipeline architecture for Google Search operations.

This module implements a flexible scraping system for Google Search results,
optimising queries and extracting useful information from search pages.
"""

from typing import List, Dict, Optional
from urllib.parse import urlparse, urlencode
from bs4 import BeautifulSoup
import warnings
import re
import time

from src.scraping.dynamic import DynamicScraper
from src.utils.logging_utils import get_logger
from src.utils.text_utils import normalise_url, extract_domain, extract_url_from_redirect
from src.utils.date_utils import calculate_search_date_params, parse_article_date

warnings.filterwarnings("ignore", category=DeprecationWarning)

class GoogleSearchScraper:
    """Google Search scraper implementation"""
    
    # Singleton instance
    # Considerations to change this once we reintegrate parallel requests on better infrastructure
    _instance = None
    _initialised = False
    
    BASE_URL = "https://www.google.com"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    # Common English stopwords to remove from search queries
    STOPWORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 
        'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between',
        'out', 'of', 'during', 'without', 'before', 'under', 'around', 'among',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'having', 'do', 'does', 'did', 'doing', 'can', 'could', 'will', 'would',
        'should', 'must', 'might', 'may', 'here', 'there', 'this', 'that',
        'these', 'those', 'am', 'from', 'whom', 'which', 'who', 'how', 'when',
        'where', 'why', 'what', 'it', 'its', 'it\'s', 'we', 'us', 'our', 'ours',
        'he', 'him', 'his', 'she', 'her', 'hers', 'they', 'them', 'their', 'theirs',
        'myself', 'yourself', 'himself', 'herself', 'itself', 'ourselves', 'yourselves',
        'themselves', 'mine', 'yours', 'all', 'both', 'some', 'any', 'most', 'more', 'no', 'nor',
    }
    
    def __new__(cls):
        # Singleton pattern
        if cls._instance is None:
            cls._instance = super(GoogleSearchScraper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Skip if already initialised
        if self._initialised:
            return
        
        # Set up logging
        self.logger = get_logger("GoogleSearchScraper")
            
        # Lazy loading for DynamicScraper
        self._dynamic_scraper = None
        self.is_dynamic_functional = True
            
        # Mark as initialised
        self.__class__._initialised = True

    @property
    def dynamic_scraper(self):
        """Lazy initialisation property for DynamicScraper"""
        if self._dynamic_scraper is None:
            self.logger.info("Initialising DynamicScraper for GoogleSearchScraper")
            try:
                self._dynamic_scraper = DynamicScraper(timeout=30)
            except Exception as e:
                self.logger.error(f"Failed to initialise DynamicScraper: {str(e)}")
                self.is_dynamic_functional = False
                return None
        return self._dynamic_scraper

    def optimise_search_query(self, query: str) -> str:
        """
        Optimise a search query by removing common stopwords and focusing on key terms.
        
        Args:
            query: Raw search query
            
        Returns:
            Optimised search query
        """
        # Skip optimisation if query is too short
        if len(query.split()) <= 3:
            return query
            
        # Save original query for logging
        original_query = query
        
        # Convert to lowercase
        query = query.lower()
        
        # Split into words and filter out stopwords
        words = query.split()
        filtered_words = [word for word in words if word not in self.STOPWORDS]
        
        # If we removed too many words, use original words
        if len(filtered_words) < 2 and len(words) > 2:
            filtered_words = words
            
        # Limit to first 4-5 important words for better search results
        # Long, specific queries often fail to find results
        if len(filtered_words) > 10:
            self.logger.info(f"Query too long ({len(filtered_words)} words), limiting to first 10 words")
            filtered_words = filtered_words[:10]
            
        # Join the words back into a query
        optimised_query = ' '.join(filtered_words)
        
        # Log the optimisation
        self.logger.info(f"Optimised query: '{original_query}' → '{optimised_query}'")
        
        return optimised_query

    # Article lookup
    def _get_article_content(self, url: str) -> Dict:
        """Get article content for a given URL using dynamic scraping if available"""
        self.logger.info(f"Getting article content from {url}")
        
        # Use dynamic scraping if available
        if self.is_dynamic_functional and self.dynamic_scraper:
            self.logger.info(f"Using dynamic scraping for {url}")
            
            try:
                # Use DynamicScraper's methods
                soup = self.dynamic_scraper.get_page_content(url)
                
                if soup:
                    return self.dynamic_scraper.extract_content(soup, url)
                else:
                    self.logger.warning(f"Dynamic scraping failed to get content for {url}")
            except Exception as e:
                self.logger.error(f"Dynamic scraping failed for {url}: {str(e)}")
        else:
            self.logger.warning(f"Dynamic scraping unavailable for {url}")
        
        # If we're here, return empty content
        return {'title': '', 'content': '', 'snippet': ''}

    def search_news(self, query: str, original_url: str = None, num_results: int = 10, 
                  days_old: int = 7, publish_date: str = None) -> List[Dict[str, str]]:
        """
        Search Google News for articles using dynamic scraping
        
        Args:
            query: Search query
            original_url: URL to exclude from results
            num_results: Number of results to return
            days_old: Default time window in days (default: 7 days)
            publish_date: Publication date of the article being analysed (optional)
        """
        try:
            # Enhanced logging and validation for the original_url parameter
            if original_url:
                self.logger.info(f"Search will filter results from domain of original URL: {original_url}")
                original_domain = extract_domain(original_url)
                self.logger.info(f"Original domain extracted: {original_domain}")
                if not original_domain:
                    self.logger.warning(f"Could not extract domain from original URL: {original_url} - domain filtering may not work")
            else:
                self.logger.info("No original URL provided - domain filtering won't be applied")
                
            # Check if query already contains date-specific information
            has_date_in_query = any(term in query for term in ["date:", "before:", "after:"])
            
            # Optimise the query for better search results
            #optimised_query = self.optimise_search_query(query)
            optimised_query = query

            # Use the optimised query
            self.logger.info(f"Searching with optimised query: {optimised_query}")
            results = self._try_search(optimised_query, original_url, num_results, days_old, 
                                      has_date_in_query, publish_date)
            
            # Log the final results for debugging
            if results:
                self.logger.info(f"Search returned {len(results)} results")
                for i, result in enumerate(results):
                    result_domain = extract_domain(result.get('url', ''))
                    self.logger.info(f"Result {i+1}: {result.get('url', '')} (Domain: {result_domain})")
            else:
                self.logger.info("Search returned no results")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in Google News search: {str(e)}")
            return []
    
    def _filter_original_article(self, results: List[Dict], original_url: str) -> List[Dict]:
        """
        Filter out results matching the original article URL or domain
        
        Args:
            results: List of search result dictionaries
            original_url: Original article URL to filter out
            
        Returns:
            Filtered list of results
        """
        filtered_results = []
        original_domain = extract_domain(original_url)
        norm_original_url = normalise_url(original_url)
        
        for result in results:
            result_url = result.get('url', '')
            if not result_url:
                continue
                
            norm_result_url = normalise_url(result_url)
            result_domain = extract_domain(result_url)
            
            # Skip if same URL or same domain
            if norm_result_url == norm_original_url or result_domain == original_domain:
                self.logger.info(f"Filtering out result {result_url} - matches original URL or domain")
                continue
                
            filtered_results.append(result)
        
        return filtered_results
    
    def _try_search(self, query: str, original_url: str = None, num_results: int = 10, 
                   days_old: int = 7, has_date_in_query: bool = False, 
                   publish_date: str = None) -> List[Dict[str, str]]:
        """
        Perform the search using dynamic scraping
        
        Args:
            query: The search query
            original_url: URL to exclude from results
            num_results: Number of results to return
            days_old: Default time window in days
            has_date_in_query: Whether query already has date parameters
            publish_date: Publication date of the article being analysed (optional)
        
        Returns:
            List of dictionaries containing article information
        """
        try:
            # Build the search URL
            search_url = self._build_search_url(query, num_results, days_old, has_date_in_query, publish_date)
            
            try:
                # Get page content using DynamicScraper
                soup = self.dynamic_scraper.get_page_content(search_url)
                
                # Check if we're on a consent page
                current_url = self.dynamic_scraper.driver.url
                if 'consent.google.com' in current_url:
                    self.logger.info("Detected Google consent page, attempting to handle it")
                    cookie_handled = self.dynamic_scraper.check_for_cookie_consent()
                    
                    if cookie_handled:
                        self.logger.info("Successfully handled Google consent page, getting updated content")
                        time.sleep(2)  # Wait for redirect after consent
                        soup = self.dynamic_scraper.get_page_soup()
                    else:
                        self.logger.warning("Failed to handle Google consent page")
                
                if soup:
                    results = self._extract_results(soup, original_url, num_results)
                    return results
                else:
                    self.logger.warning(f"Dynamic scraping returned no content")
            except Exception as e:
                self.logger.error(f"Error in dynamic scraping: {str(e)}")
            
            # If we get here, all dynamic scraping attempts failed
            self.logger.error("All dynamic scraping attempts failed")
            return []
                
        except Exception as e:
            self.logger.error(f"Error in search: {str(e)}")
            return []
            
    def _build_search_url(self, query: str, num_results: int, days_old: int, 
                         has_date_in_query: bool, publish_date: str) -> str:
        """
        Build the Google search URL with appropriate parameters
        
        Args:
            query: Search query
            num_results: Number of results to request
            days_old: Default time window in days
            has_date_in_query: Whether query already has date parameters
            publish_date: Publication date of the article being analysed (optional)
            
        Returns:
            Complete search URL
        """
        search_url = f"{self.BASE_URL}/search"
        params = {
            'hl': 'en',  # Set language to English
            'q': query,
            'tbm': 'nws',  # Search for news
            'num': num_results,  # Number of results to return
        }
        
        # Handle date parameters based on article publication date and default days_old setting
        if not has_date_in_query:
            # Use date utility to calculate appropriate search date parameters
            date_params = calculate_search_date_params(publish_date, days_old)
            if date_params:
                params.update(date_params)
                self._log_date_parameters(publish_date, days_old)
                
        search_url = f"{search_url}?{urlencode(params)}"
        self.logger.info(f"Search URL: {search_url}")
        return search_url
        
    def _log_date_parameters(self, publish_date: str, days_old: int) -> None:
        """
        Log information about date parameters being used for search
        
        Args:
            publish_date: Publication date of the article being analysed
            days_old: Default time window in days
        """
        article_date = parse_article_date(publish_date)
        if article_date:
            # Get the month names for easier reading in logs
            months = ["January", "February", "March", "April", "May", "June", 
                     "July", "August", "September", "October", "November", "December"]
            
            # Format the publication date for logging
            pub_date_str = f"{article_date.year}-{article_date.month:02d}-{article_date.day:02d}"
            
            # Calculate start and end months
            start_month = article_date.month
            start_month_year = article_date.year
            
            end_month = start_month + 1
            end_month_year = start_month_year
            if end_month > 12:
                end_month = 1
                end_month_year += 1
            
            # Get month names
            start_month_name = months[start_month - 1]
            end_month_name = months[end_month - 1]
            
            self.logger.info(f"Article published on {pub_date_str}, searching from {start_month_name} {start_month_year} to end of {end_month_name} {end_month_year}")
        else:
            self.logger.info(f"No article date detected, using default {days_old} days window")
    
    def _extract_results(self, soup: BeautifulSoup, original_url: str, num_results: int) -> List[Dict[str, str]]:
        """
        Extract search results from soup object using a focused approach
        based on Google's consistent news result structure
        
        Args:
            soup: BeautifulSoup object containing the search results page
            original_url: URL to exclude from results 
            num_results: Maximum number of results to return
            
        Returns:
            List of dictionaries containing article information
        """
        results = []
        
        # Track original URL information if provided
        original_url_info = self._get_original_url_info(original_url)
        original_domain = original_url_info.get('domain') if original_url_info else None
        
        # Enhanced logging for debugging domain filtering
        self.logger.info(f"Original URL: {original_url}")
        self.logger.info(f"Original domain extracted: {original_domain}")
        
        # Set to track URLs we've already processed to avoid duplicates
        processed_urls = set()
    
        try:
            # Find all elements with data-news attributes 
            news_items = soup.find_all(lambda tag: tag.name == 'div' and tag.has_attr('data-news-cluster-id'))
            self.logger.info(f"Found {len(news_items)} potential news items")
            
            # Process each news item
            for item in news_items:
                try:
                    # Primary link
                    link = None
                    
                    # First look for the main headline link
                    links = item.find_all('a')
                    if not links:
                        continue
                        
                    # Find the most prominent link - the first with href and ping attributes
                    for a in links:
                        if a.has_attr('href') and a.has_attr('ping'):
                            link = a
                            break
                  
                    if not link or not link.has_attr('href'):
                        continue
                    
                    # Extract URL
                    url = link['href']
                    
                    # Handle Google redirect URLs
                    if url.startswith('/url?') or 'google.com/url' in url:
                        try:
                            url = extract_url_from_redirect(url)
                        except Exception as e:
                            self.logger.warning(f"Error extracting URL from redirect: {str(e)}")
                            continue
                    
                    if not url.startswith('http'):
                        continue
                    
                    # Skip if should be skipped
                    if self._should_skip_url(url, original_url_info, processed_urls):
                        continue

                    # Check if the domain matches the original article's domain
                    if original_domain:
                        current_domain = extract_domain(url)
                        self.logger.info(f"Comparing domains - Result URL: {url}, Domain: {current_domain}, Original Domain: {original_domain}")
                        if current_domain == original_domain:
                            self.logger.info(f"FILTERED: Skipping URL from same domain as original article: {url}")
                            continue
                    
                    # Find the title
                    title = ""
                    
                    # Check for heading roles 
                    heading_elem = item.find(attrs={"role": "heading"}) # Google news results have a heading role
                    if heading_elem:
                        title = heading_elem.get_text().strip()

                    # If that doesn't work, try the link text itself
                    if not title and link.string:
                        title = link.string.strip()
                    
                    # Add to results
                    processed_urls.add(url)
                    results.append({
                        'url': url,
                        'title': title
                    })
                    self.logger.info(f"Added news result: {url} - {title}")
                    
                    # Stop if we have enough results
                    if len(results) >= num_results:
                        return results
                
                except Exception as e:
                    self.logger.warning(f"Error processing news item: {str(e)}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error extracting news results: {str(e)}")
        
        return results
        
    def _get_original_url_info(self, original_url: str) -> Optional[Dict]:
        """
        Extract information about the original URL for filtering
        
        Args:
            original_url: URL to extract information from
            
        Returns:
            Dictionary with domain and normalised URL, or None if not provided
        """
        if not original_url:
            return None
            
        try:
            return {
                'domain': extract_domain(original_url),
                'normalised_url': normalise_url(original_url)
            }
        except:
            self.logger.warning(f"Could not parse original URL: {original_url}")
            return None

    def _should_skip_url(self, url: str, original_url_info: Optional[Dict], processed_urls: set) -> bool:
        """
        Check if a URL should be skipped
        
        Args:
            url: URL to check
            original_url_info: Information about the original URL to filter out
            processed_urls: Set of already processed URLs
            
        Returns:
            True if URL should be skipped, False otherwise
        """
        # Skip if we've already processed this URL
        if url in processed_urls:
            return True
            
        # Skip if this is the original URL using normalised comparison
        if original_url_info:
            url_normalised = normalise_url(url)
            if url_normalised == original_url_info['normalised_url']:
                self.logger.info(f"Skipping URL - same as original article: {url}")
                return True
                
        # Skip unwanted domains - blacklist
        # could add more in the future
        blacklisted_domains = [
            'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
            'policies.google.com' 
        ]
        
        if any(domain in url.lower() for domain in blacklisted_domains):
            self.logger.info(f"Skipping blacklisted domain: {url}")
            return True
            
        return False

    def cleanup(self):
        """
        Clean up resources used by the scraper.
        
        Should be called when the scraper is no longer needed
        or before application shutdown.
        """
        self.logger.info("Cleaning up GoogleSearchScraper resources")
        
        # Clean up DynamicScraper if it was initialised
        if hasattr(self, '_dynamic_scraper') and self._dynamic_scraper is not None:
            try:
                self._dynamic_scraper.cleanup()
                self._dynamic_scraper = None
                self.logger.info("DynamicScraper resources released")
            except Exception as e:
                self.logger.error(f"Error cleaning up DynamicScraper: {str(e)}")
            
        # Reset dynamic scraper functionality flag
        self.is_dynamic_functional = True
        
        # Reset instance variables
        self.__class__._initialised = False
        self.logger.info("GoogleSearchScraper cleanup completed successfully")

    def __del__(self):
        """Clean up resources when the scraper is destroyed"""
        try:
            self.cleanup()
        except:
            pass

