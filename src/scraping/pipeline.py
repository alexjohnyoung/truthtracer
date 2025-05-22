import logging
import time
import traceback
from typing import Dict, List, Optional, Callable, Any, Union
from urllib.parse import urlparse

from src.utils.logging_utils import get_logger
from src.utils.text_utils import extract_domain
from src.utils.content_validator import ContentValidator
from .static import StaticScraper
from .dynamic import DynamicScraper
from src.processing.metadata_extractor import MetadataExtractor
from src.processing.content_extractor import ContentExtractor
from src.processing.text_cleaner import TextCleaner
from .domain_rules import DomainRules
from src.google.google import GoogleSearchScraper

class PipelineStage:
    """
    Represents a single stage in the scraping pipeline.
    Each stage has a processor function and error handling.
    """
    
    def __init__(
        self, 
        name: str, 
        processor: Callable, 
        error_handler: Optional[Callable] = None,
        retry_attempts: int = 1,
        retry_delay: int = 2
    ):
        """
        Initialise a pipeline stage.
        
        Args:
            name: Name of the stage
            processor: Function that implements the stage's logic
            error_handler: Optional function to handle errors in this stage
            retry_attempts: Number of retry attempts if stage fails
            retry_delay: Delay between retry attempts in seconds
        """
        self.name = name
        self.processor = processor
        self.error_handler = error_handler
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
    def execute(self, context: Dict, logger: logging.Logger) -> bool:
        """
        Execute this pipeline stage with retry logic.
        
        Args:
            context: Pipeline context containing all state
            logger: Logger for this pipeline
            
        Returns:
            Boolean indicating success or failure
        """
        attempt = 0
        tag = f"[Stage:{self.name}]"
        
        while attempt <= self.retry_attempts:
            try:
                if attempt > 0:
                    logger.info(f"{tag} Retry attempt {attempt}")
                    
                # Execute the processor with the context
                result = self.processor(context)
                
                # Store result in context if not None
                if result is not None:
                    context['results'][self.name] = result
                    
                # Signal successful completion
                logger.info(f"{tag} Completed successfully")
                return True
                
            except Exception as e:
                attempt += 1
                logger.error(f"{tag} Error: {str(e)}")
                logger.debug(f"{tag} Traceback: {traceback.format_exc()}")
                
                # Try error handler if available
                if self.error_handler:
                    try:
                        handled = self.error_handler(context, e)
                        if handled:
                            logger.info(f"{tag} Error handled successfully")
                            return True
                    except Exception as handler_error:
                        logger.error(f"{tag} Error handler failed: {str(handler_error)}")
                
                # If we have retry attempts left, wait and retry
                if attempt <= self.retry_attempts:
                    logger.info(f"{tag} Will retry in {self.retry_delay}s ({attempt}/{self.retry_attempts})")
                    time.sleep(self.retry_delay)
                    # Incrementally increase delay for subsequent retries
                    self.retry_delay = min(self.retry_delay * 2, 30)  # Max 30s delay
                else:
                    logger.error(f"{tag} Failed after {attempt} attempts")
                    return False
                    
        return False


class ScrapingPipeline:
    """
    Pipeline architecture for web scraping operations.
    Orchestrates the entire scraping process through stages. 
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialise the pipeline with all required components
        
        Args:
            timeout: Timeout in seconds for scraping operations
            max_retries: Maximum number of retries for scraping operations
        """
        # Store configuration parameters
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Set up components
        self.static_scraper = StaticScraper(timeout=self.timeout)
        self.metadata_extractor = MetadataExtractor()
        self.content_extractor = ContentExtractor()
        self.text_cleaner = TextCleaner()
        
        # Configure logging using centralized utility
        self.logger = get_logger(__name__)
        self.tag = "[Pipeline]"
        
        # Define the pipeline stages
        self.stages = []
        self._define_pipeline()
        
        # Lazy initialisation
        self._google_scraper = None
        self._dynamic_scraper = None

    @property
    def dynamic_scraper(self):
        """Lazy initialization property for DynamicScraper"""
        if self._dynamic_scraper is None:
            self.log("Initializing DynamicScraper")
            self._dynamic_scraper = DynamicScraper(timeout=self.timeout)
        return self._dynamic_scraper
    
    @property
    def google_scraper(self):
        """Lazy initialization property for GoogleSearchScraper"""
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
            
    def _define_pipeline(self):
        """Define the standard pipeline stages"""
        
        # Stage 1: Domain Analysis
        self.stages.append(PipelineStage(
            name="domain_analysis",
            processor=self._process_domain_analysis,
            retry_attempts=0  # No retry needed for analysis
        ))
        
        # Stage 2: Static Scraping (conditional)
        self.stages.append(PipelineStage(
            name="static_scraping",
            processor=self._process_static_scraping,
            error_handler=self._handle_static_scraping_error,
            retry_attempts=min(1, self.max_retries)  # Use configured retry setting
        ))
        
        # Stage 3: Dynamic Scraping (conditional)
        self.stages.append(PipelineStage(
            name="dynamic_scraping",
            processor=self._process_dynamic_scraping,
            error_handler=self._handle_dynamic_scraping_error,
            retry_attempts=min(2, self.max_retries),  # Use configured retry setting
            retry_delay=3
        ))
        
        # Stage 4: Content Extraction
        self.stages.append(PipelineStage(
            name="content_extraction",
            processor=self._process_content_extraction,
            retry_attempts=min(1, self.max_retries)  # Use configured retry setting
        ))
        
        # Stage 5: Metadata Extraction
        self.stages.append(PipelineStage(
            name="metadata_extraction",
            processor=self._process_metadata_extraction,
            retry_attempts=1
        ))
        
        # Stage 6: Content Cleaning
        self.stages.append(PipelineStage(
            name="content_cleaning",
            processor=self._process_content_cleaning,
            retry_attempts=0  # No retry needed for cleaning
        ))
        
        # Stage 7: Content Validation
        self.stages.append(PipelineStage(
            name="content_validation",
            processor=self._process_content_validation,
            retry_attempts=0  # No retry needed for validation
        ))
        
    # Pipeline processor functions
        
    def _process_domain_analysis(self, context: Dict) -> Dict:
        """
        Analyse domain and apply domain-specific rules
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with domain analysis results
        """
        url = context.get('url')
        domain = extract_domain(url)
        
        # Store domain in context
        context['domain'] = domain
        
        # Check if domain is blocked
        if DomainRules.is_blocked(domain):
            self.log(f"Domain is blocked: {domain}")
            context['blocked'] = True
            context['skip_remaining_stages'] = True
            return {'blocked': True, 'domain': domain}
            
        return {
            'domain': domain
        }
    
        # TODO: Add more domain analysis stuff
        
    def _process_static_scraping(self, context: Dict) -> Dict:
        """
        Perform static scraping unless skipped
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with static scraping results
        """
        url = context.get('url')
    
        self.log(f"Attempting static scraping for {url}")
        soup, requires_js = self.static_scraper.get_page_content(url)

        if soup:
            context['soup'] = soup
            html_size = len(str(soup))
            self.log(f"Static scraping returned content of size: {html_size} bytes")
            
            # Check if this is a valid page 
            if ContentValidator.has_meaningful_content(soup):
                self.log("Page has meaningful content, don't need dynamic scraping")
                return {'success': True, 'html_size': html_size}
            
            # Check if content requires JavaScript
            if requires_js:
                self.log("Content requires JavaScript, will need dynamic scraping")
                context['requires_dynamic'] = True
                context['static_failed'] = True
                return {'failed': True, 'reason': 'requires_javascript'}
                
            return {'success': True, 'html_size': html_size}
        else:
            self.log("Static scraping failed to return content")
            context['static_failed'] = True
            context['requires_dynamic'] = True
            raise ValueError("Static scraping failed to return content")
            
    def _handle_static_scraping_error(self, context: Dict, error: Exception) -> bool:
        """
        Handle errors in static scraping
        
        Args:
            context: Pipeline context
            error: The exception that occurred
            
        Returns:
            Boolean indicating if error was handled
        """
        self.log(f"Static scraping error: {str(error)}", level='warning')
        
        # Mark static scraping as failed
        context['static_failed'] = True
        
        self.log("Will attempt dynamic scraping as fallback")
        
        # Continue with pipeline
        return True
        
    def _process_dynamic_scraping(self, context: Dict) -> Dict:
        """
        Try dynamic scraping if static scraping fails or indicates JS is needed
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with scraping results
        """
        # Skip if static scraping was successful and doesn't require dynamic
        if not context.get('static_failed', False):
            self.log("Skipping dynamic scraping as static was successful")
            context['dynamic_skipped'] = True
            return {'skipped': True}
            
        url = context.get('url')
        
        self.log(f"Attempting dynamic scraping for {url}")

        try:
            self.log(f"Getting page content for {url}")
            soup = self.dynamic_scraper.get_page_content(url, cleanup_after=False)
            
            if not soup:
                self.log("Dynamic scraping failed to return content", level='error')
                raise ValueError("Dynamic scraping failed to return content")

            # Store the soup in context
            context['soup'] = soup
            html_size = len(str(soup))
            self.log(f"Dynamic scraping returned content of size: {html_size} bytes")
            self.dynamic_scraper.cleanup()
            return {'success': True, 'html_size': html_size, 'cookie_handled': False}
            
        except Exception as e:
            self.log(f"Error during dynamic scraping: {str(e)}", level='error')
            context['dynamic_failed'] = True
            self.dynamic_scraper.cleanup()
            raise ValueError(f"Dynamic scraping failed: {str(e)}")
        
    def _handle_dynamic_scraping_error(self, context: Dict, error: Exception) -> bool:
        """
        Handle errors in dynamic scraping
        
        Args:
            context: Pipeline context
            error: The exception that occurred
            
        Returns:
            Boolean indicating if error was handled
        """
        self.log(f"Dynamic scraping error: {str(error)}", level='warning')
        
        # TODO: Add stable recovery mechanism 
        # Previously we had a recovery mechanism that would try to recover from the error
        # But this was found to be unreliable and prone to causing more problems than it solved
        # The issue is that there are many different types of errors that can occur and it's hard to predict which ones will recover
        # So we're just going to fail outright at this point
        return False
            
    def _process_content_extraction(self, context: Dict) -> Dict:
        """
        Extract main content from page
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with content extraction results
        """
        soup = context.get('soup')
        if not soup:
            raise ValueError("No soup available for content extraction")
            
        url = context.get('url')
        
        # Extract content
        content = self.content_extractor.extract_content(soup, url)
        if not content:
            self.log("Content extraction failed", level='warning')
            raise ValueError("Failed to extract content")
            
        # Store in context
        context['content'] = content
        
        # Get stats for logging
        text_length = len(content.get('text', ''))
        links_count = len(content.get('links', []))
        
        self.log(f"Extracted {text_length} chars of text and {links_count} links")
        
        return {
            'text_length': text_length,
            'links_count': links_count
        }
        
    def _process_metadata_extraction(self, context: Dict) -> Dict:
        """
        Extract metadata from page
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with metadata extraction results
        """
        soup = context.get('soup')
        if not soup:
            raise ValueError("No soup available for metadata extraction")
            
        url = context.get('url')
        content = context.get('content', {})
        
        # Extract metadata
        self.metadata_extractor.extract_metadata(soup, url, content)
        
        # Update context with the updated content (which now has metadata)
        context['content'] = content
        
        self.log(f"Extracted metadata - Headline: {content.get('headline', '')[:50]}...")
        
        return {
            'headline': bool(content.get('headline')),
            'author': bool(content.get('author')),
            'publishDate': bool(content.get('publishDate'))
        }
        
    def _process_content_cleaning(self, context: Dict) -> Dict:
        """
        Clean extracted content
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with cleaning results
        """
        content = context.get('content', {})
        if not content:
            raise ValueError("No content available for cleaning")
            
        # Get original lengths for comparison
        original_text_length = len(content.get('text', ''))

        # Clean the content text
        if 'text' in content and content['text']:
            content['text'] = self.text_cleaner.clean_content(content['text'])
            
        # Clean author
        if 'author' in content and content['author']:
            content['author'] = self.text_cleaner.clean_author_text(content['author'])
            
        # Clean date
        if 'publishDate' in content and content['publishDate']:
            content['publishDate'] = self.text_cleaner.clean_date_text(content['publishDate'])
            
        # Update context
        context['content'] = content
        
        # Get new lengths
        cleaned_text_length = len(content.get('text', ''))
        
        self.log(f"Cleaned content text from {original_text_length} to {cleaned_text_length} chars")
        
        return {
            'original_length': original_text_length,
            'cleaned_length': cleaned_text_length,
            'text_reduction': original_text_length - cleaned_text_length
        }
        
    def _process_content_validation(self, context: Dict) -> Dict:
        """
        Validate final content quality
        
        Args:
            context: Pipeline context
            
        Returns:
            Dictionary with validation results
        """
        content = context.get('content', {})
        if not content:
            self.log("No content to validate", level='warning')
            context['validated'] = False
            return {'valid': False, 'reason': 'no_content'}
            
        # Check headline
        headline = content.get('headline', '')
        if not headline:
            self.log("Content validation warning: missing headline", level='warning')
            # Don't fail just because of missing headline
            
        # Content passed validation
        context['validated'] = True
        
        # Get text for logging
        text = content.get('text', '')
        self.log(f"Content passed validation: {len(text)} chars, headline present: {bool(headline)}")
        
        # TODO: Add more validation checks here
        
        return {
            'valid': True,
            'text_length': len(text),
            'has_headline': bool(headline),
            'has_author': bool(content.get('author')),
            'has_date': bool(content.get('publishDate'))
        }
        
    def scrape(self, url: str) -> Optional[Dict]:
        """
        Main entry point to scrape content from a URL
        
        Args:
            url: URL to scrape
            
        Returns:
            Dictionary containing the scraped content or None if failed
        """
        self.log(f"Starting scraping pipeline for {url}")
        
        # Initialise pipeline context
        context = {
            'url': url,
            'start_time': time.time(),
            'results': {}
        }
        
        # Execute pipeline stages
        for stage in self.stages:
            # Skip remaining stages if indicated
            if context.get('skip_remaining_stages', False):
                self.log(f"Skipping remaining stages from stage '{stage.name}'")
                break
                
            self.log(f"Executing stage: {stage.name}")
            success = stage.execute(context, self.logger)
            
            if not success:
                self.log(f"Pipeline failed at stage: {stage.name}", level='error')
                return None
                
        # Calculate pipeline execution time
        execution_time = time.time() - context['start_time']
        self.log(f"Pipeline completed in {execution_time:.2f} seconds")
        
        # Return the final content
        if context.get('validated', False):
            return context.get('content')
        else:
            self.log("Pipeline completed but content validation failed", level='warning')
            return None
            
    def search_for_articles(self, query: str, original_url: str = None, days_old: int = 7, num_results: int = 10, publish_date: str = None) -> List[Dict[str, str]]:
        """
        Search for news articles
        
        Args:
            query: The search query
            original_url: URL to exclude from results (same domain will be filtered)
            days_old: How many days old the articles can be (default: 7)
            num_results: Maximum number of results to return
            publish_date: Publication date of the article being analysed (optional)
            
        Returns:
            List of dictionaries containing article information
        """
        self.log(f"Search query: '{query}'")
        
        if self.google_scraper:
            return self.google_scraper.search_news(
                query=query,
                original_url=original_url,
                days_old=days_old,
                num_results=num_results,
                publish_date=publish_date
            )
        else:
            self.log("GoogleSearchScraper not available", level="error")
            return []

    def cleanup(self):
        """
        Clean up all resources used by the pipeline.
        
        This should be called when the pipeline is no longer needed or
        before application shutdown.
        """
        self.log("Cleaning up ScrapingPipeline resources")
        
        try:
            if hasattr(self, 'static_scraper') and self.static_scraper is not None:
                self.static_scraper.cleanup()
                self.log("Successfully cleaned up StaticScraper")
        except Exception as e:
            self.log(f"Error cleaning up StaticScraper: {str(e)}", level='error')
        
        try:
            if hasattr(self, '_dynamic_scraper') and self._dynamic_scraper is not None:
                self._dynamic_scraper.cleanup()
                self.log("Successfully cleaned up DynamicScraper")
                self._dynamic_scraper = None
        except Exception as e:
            self.log(f"Error cleaning up DynamicScraper: {str(e)}", level='error')
            
        try:
            if hasattr(self, '_google_scraper') and self._google_scraper is not None:
                if hasattr(self._google_scraper, 'cleanup'):
                    self._google_scraper.cleanup()
                    self.log("Successfully cleaned up GoogleSearchScraper")
                self._google_scraper = None
        except Exception as e:
            self.log(f"Error cleaning up GoogleSearchScraper: {str(e)}", level='error')
        
        self.log("ScrapingPipeline cleanup completed")
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            self.cleanup()
        except Exception:
            pass
