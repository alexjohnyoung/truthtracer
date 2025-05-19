from typing import Dict, List, Optional, Tuple, Any
from baml_client.async_client import b
from baml_client.types import ArticleAnalysis, MisleadingAnalysis
from src.utils.logging_utils import get_logger
from src.utils.text_utils import normalise_url, extract_domain
from src.utils.status import update_status
from src.scraping.controller import ScrapingController
from src.processing.text_cleaner import TextCleaner
from src.google.google import GoogleSearchScraper
from src.utils.date_utils import format_date_for_display

class NewsProcessor:
    """
    Processes news articles for analysis and cross-referencing.
    
    This class handles:
    1. Article content processing with LLM models
    2. Extraction of claims and summaries
    3. Cross-referencing with other articles for fact-checking
    """
    
    def __init__(self, scraping_controller=None):
        """
        Initialise the news processor with optionally injected dependencies
        
        Args:
            scraping_controller: Optional ScrapingController instance. If not provided,
                                a new instance will be created when needed.
        """
        # Configure logging using the centralized utility
        self.logger = get_logger(__name__)
        self._scraping_controller = scraping_controller
        
    @property
    def scraping_controller(self):
        if self._scraping_controller is None:
            self.logger.info("Initialising ScrapingController")
            self._scraping_controller = ScrapingController()
        return self._scraping_controller

    def cleanup(self):
        """
        Clean up resources used by the NewsProcessor.
        
        This should be called when the processor is no longer needed or
        before application shutdown.
        """
        self.logger.info("Cleaning up NewsProcessor resources")
        
        # Clean up ScrapingController if it was created by this instance
        if hasattr(self, '_scraping_controller') and self._scraping_controller is not None:
            try:
                self._scraping_controller.cleanup()
                self.logger.info("Successfully cleaned up ScrapingController")
            except Exception as e:
                self.logger.error(f"Error cleaning up ScrapingController: {str(e)}")
        
        self.logger.info("NewsProcessor cleanup completed")
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            self.cleanup()
        except:
            pass

    def get_search_query(self, headline: str) -> str:
        """
        Create a search query from the headline, using an optimised version for better results
        
        Args:
            headline: Article headline to create search query from
            
        Returns:
            Optimised search query based on headline
        """
        # Remove any site: operators from the headline
        cleaned_headline = headline.replace('site:', '').strip()
        
        # Ensure the query isn't too long (Google has limits)
        if len(cleaned_headline) > 200:
            cleaned_headline = cleaned_headline[:197] + "..."
        
        # Try to use the GoogleSearchScraper's optimisation if available
        try:
            google_scraper = GoogleSearchScraper()
            return google_scraper.optimise_search_query(cleaned_headline)
        except AttributeError as e:
            # If optimisation fails for any reason, fall back to the original headline
            self.logger.warning(f"Could not optimise search query: {str(e)}")
            return cleaned_headline

    async def process_article(self, text: str, is_main_article: bool = True) -> Optional[ArticleAnalysis]:
        """
        Process article text using BAML
        
        Args:
            text: The article text to process
            is_main_article: Whether this is the main article (True) or a reference article (False)
            
        Returns:
            ArticleAnalysis object or None if processing failed
        """
        article_type = "main" if is_main_article else "reference"
        try:
            if not text or len(text.strip()) == 0:
                self.logger.error(f"{article_type.capitalize()} article text is too short or empty")
                if is_main_article:
                    update_status("Article text is empty or too short", 20, "Error", -1)
                return None
            
            if is_main_article:
                update_status("Preparing article text for analysis", 18, "Text Processing", 2)
                char_count = len(text)
                update_status(f"Processing {char_count} characters of text", 19, "Text Processing", 2)
            
            # Use TextCleaner to clean the article
            cleaned_text = await TextCleaner.clean_article_with_llm(text)
            
            if is_main_article:
                update_status("Article text cleaned successfully", 21, "Text Processing", 2)
                update_status("Starting LLM analysis of article content", 22, "AI Analysis", 2)
            
            try:
                # Extract claims and summary using the BAML function
                if is_main_article:
                    update_status("Extracting article claims", 24, "Claims Extraction", 2)
                
                result = await b.ExtractArticleInfo(cleaned_text)
                
                if is_main_article:
                    update_status("Generating article summary", 27, "Summary Generation", 2)
                    claims_count = len(getattr(result, 'claims', []))
                    update_status(f"Completed article analysis with {claims_count} claims identified", 29, "Claims Extraction", 2)
                
                return result
              
            except Exception as e:
                self.logger.error(f"Error in LLM extraction: {str(e)}")
                if is_main_article:
                    update_status(f"Error analyzing article content: {str(e)[:100]}", 30, "Error", -1)
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing {article_type} article: {str(e)}")
            if is_main_article:
                update_status(f"Error processing article: {str(e)[:100]}", 30, "Error", -1)
            return None

    async def cross_reference_articles(
        self, 
        main_article: Tuple[ArticleAnalysis, Dict], 
        reference_articles: List[Tuple[ArticleAnalysis, Dict]]
    ) -> Tuple[Optional[MisleadingAnalysis], Optional[Dict]]:
        """
        Cross-reference the main article with reference articles to detect misleading content
        
        Args:
            main_article: Tuple containing ArticleAnalysis and metadata
            reference_articles: List of tuples containing ArticleAnalysis and metadata
            
        Returns:
            Tuple containing:
                - MisleadingAnalysis object
                - Dictionary containing additional analysis data
        """
        try:
            if not main_article or not main_article[0] or not reference_articles:
                self.logger.warning("Missing data for cross-reference analysis")
                update_status("Cross-reference skipped: Missing article data", 80, "Cross-Reference", 5)
                return None, None
                
            article_data, article_meta = main_article
            
            # Extract all reference articles that have valid data
            valid_refs = [(ref_data, ref_meta) for ref_data, ref_meta in reference_articles if ref_data]
            
            if not valid_refs:
                self.logger.warning("No valid reference articles for comparison")
                update_status("Cross-reference skipped: No valid reference articles", 80, "Cross-Reference", 5)
                return None, None
                
            update_status(f"Starting cross-reference with {len(valid_refs)} articles", 77, "Cross-Reference", 5)
                
            # Get main article title and reference titles from metadata
            main_title = article_meta.get('headline', '') if isinstance(article_meta, dict) else getattr(article_meta, 'headline', '')
            
            ref_titles = []
            for ref_data, ref_meta in valid_refs:
                if isinstance(ref_meta, dict):
                    ref_titles.append(ref_meta.get('headline', ''))
                else:
                    ref_titles.append(getattr(ref_meta, 'headline', ''))
            
            # Extract just the reference data objects
            ref_articles = [ref_data for ref_data, _ in valid_refs]
            
            update_status("Extracting claims for comparison", 78, "Cross-Reference", 5)
            update_status("Comparing article claims with reference sources", 79, "Cross-Reference", 5)
            
            # Run the cross-reference analysis
            try:
                self.logger.info(f"Analysing misleading content across {len(ref_articles)} reference articles")
                
                update_status("Analyzing article for potential misleading content", 80, "Cross-Reference", 5)
                
                result = await b.AnalyseMisleadingContent(
                    article=article_data,
                    referenceArticles=ref_articles,
                    mainTitle=main_title,
                    referenceTitles=ref_titles
                )
                
                # Validate the result has the expected fields
                if not hasattr(result, 'isMisleading') or not hasattr(result, 'explanation'):
                    self.logger.error("Invalid response format")
                    update_status("Cross-reference failed: Invalid analysis format", 82, "Cross-Reference Error", 5)
                    return None, None
                
                # Report the result of the analysis
                if hasattr(result, 'isMisleading'):
                    if result.isMisleading:
                        update_status("Completed analysis: Potentially misleading content detected", 82, "Cross-Reference", 5)
                    else:
                        update_status("Completed analysis: No misleading content detected", 82, "Cross-Reference", 5)
                
                return result, {
                    "mainTitle": main_title,
                    "refTitles": ref_titles,
                    "refCount": len(ref_articles)
                }
                
            except Exception as e:
                if "BamlValidationError" in str(e) or "Failed to parse LLM response" in str(e):
                    self.logger.error(f"LLM parsing error: {str(e)}")
                    update_status("AI analysis error: Unable to evaluate article reliability", 82, "Cross-Reference Error", 5)
                    # Return a fallback "neutral" result instead of None
                    fallback_result = type('MisleadingAnalysisFallback', (), {
                        'isMisleading': None,
                        'reasons': ["AI analysis format error"],
                        'explanation': "Our AI had trouble analysing this article. This doesn't mean the article is misleading - just that our system couldn't properly evaluate it."
                    })()
                    return fallback_result, {
                        "mainTitle": main_title,
                        "refTitles": ref_titles,
                        "refCount": len(ref_articles),
                        "analysis_error": str(e)
                    }
                
                self.logger.error(f"Error in cross-reference analysis: {str(e)}")
                update_status(f"Cross-reference error: {str(e)[:100]}", 82, "Cross-Reference Error", 5)
                return None, None
                
        except Exception as e:
            self.logger.error(f"Error setting up cross-reference: {str(e)}")
            update_status(f"Cross-reference setup error: {str(e)[:100]}", 82, "Cross-Reference Error", 5)
            return None, None

    async def process_reference_articles(self, reference_results, main_url):
        """
        Process a list of reference articles
        
        Args:
            reference_results: List of reference article search results
            main_url: Normalised URL of the main article to avoid self-reference
            
        Returns:
            Tuple containing (processed_references dict, list of reference analyses)
        """
        processed_references = {
            "successful": [],
            "skipped": []
        }
        
        reference_analyses = []
 
        total_refs = len(reference_results)
        update_status(f"Preparing to process {total_refs} reference articles", 60, "Reference Analysis", 4)
        
        for idx, ref in enumerate(reference_results):
            ref_url = ref.get('url')
            ref_title = ref.get('title', 'Unknown Title')
            
            # Calculate progress based on current article index
            progress = 60 + int((idx / max(1, total_refs)) * 20)  # Progress from 60-80%
            update_status(f"Processing reference {idx+1}/{total_refs}: {ref_title}", 
                            progress, "Reference Analysis", 4)
            
            if not ref_url:
                processed_references["skipped"].append({
                    "url": "unknown",
                    "title": ref_title,
                    "reason": "Missing URL"
                })
                update_status(f"Skipped reference {idx+1}: Missing URL", progress, "Reference Analysis", 4)
                continue
            
            # Skip if it's the same as the main article
            if normalise_url(ref_url) == main_url:
                processed_references["skipped"].append({
                    "url": ref_url,
                    "title": ref_title,
                    "reason": "Same as main article"
                })
                update_status(f"Skipped reference {idx+1}: Same as main article", progress, "Reference Analysis", 4)
                continue
            
            try:
                # Scrape and process reference article
                domain = extract_domain(ref_url)
                update_status(f"Scraping reference {idx+1}: {domain}", 
                                progress, "Reference Scraping", 4)
                
                ref_content = self.scraping_controller.scrape_content(ref_url)
                
                if not ref_content or not ref_content.get('text'):
                    processed_references["skipped"].append({
                        "url": ref_url,
                        "title": ref_title,
                        "reason": "Failed to scrape content"
                    })
                    update_status(f"Failed to scrape reference {idx+1} from {domain}", progress, "Reference Analysis", 4)
                    continue
              
                update_status(f"Analysing reference {idx+1}: {ref_title}", 
                                progress+1, "Reference Analysis", 4)
                
                ref_analysis = await self.process_article(ref_content['text'], is_main_article=False)
                
                if not ref_analysis:
                    processed_references["skipped"].append({
                        "url": ref_url,
                        "title": ref_title,
                        "reason": "Failed to process content"
                    })
                    update_status(f"Failed to analyse reference {idx+1}: {ref_title}", progress+1, "Reference Analysis", 4)
                    continue
                
                # Create a base metadata object with search result data
                base_metadata = {
                    'headline': ref.get('title', 'Unknown Title'),
                    'source': extract_domain(ref_url),
                    'publishDate': ref.get('publishDate')
                }
                
                # Merge with scraping metadata 
                # We're doing this incase the result metadata is not complete
                if ref_content:
                    self._merge_metadata(base_metadata, ref_content)
                
                # Format the publication date for display
                formatted_date = format_date_for_display(base_metadata.get('publishDate', ''))
                
                # Add to reference analyses for cross-referencing
                reference_analyses.append((ref_analysis, base_metadata))
                
                # Report on claims found in reference article
                claims_count = len(getattr(ref_analysis, 'claims', []))
                
                # Add to successful references
                processed_references["successful"].append({
                    "url": ref_url,
                    "headline": base_metadata.get('headline', ref.get('title', 'Unknown Title')),
                    "source": extract_domain(ref_url),
                    "publishDate": formatted_date,
                    "author": base_metadata.get('author', 'Unknown'),
                    "analysis": {
                        "claims": getattr(ref_analysis, 'claims', []),
                        "summary": getattr(ref_analysis, 'summary', '')
                    }
                })
                
               
                update_status(f"Successfully processed reference {idx+1}/{total_refs} with {claims_count} claims", 
                                 progress+2, "Reference Analysis", 4)
                
            except Exception as e:
                self.logger.error(f"Error processing reference article {ref_url}: {str(e)}")
                processed_references["skipped"].append({
                    "url": ref_url,
                    "title": ref_title,
                    "reason": f"Processing error: {str(e)[:100]}"
                })
                update_status(f"Error processing reference {idx+1}: {str(e)[:100]}", progress, "Reference Error", 4)
        
        # Final update for reference processing
        success_count = len(processed_references["successful"])
        skipped_count = len(processed_references["skipped"])
        update_status(f"Completed reference processing: {success_count} successful, {skipped_count} skipped", 
                        80, "Reference Complete", 4)
        
        return processed_references, reference_analyses

    def _build_analysis_result(self, url, article_analysis, metadata, processed_references, max_references, cross_reference_result=None, cross_reference_meta=None):
        """
        Build the final analysis result dictionary
        
        Args:
            url: The URL of the article that was analysed
            article_analysis: The main article analysis object
            metadata: Metadata for the main article
            processed_references: Dictionary of processed reference articles
            max_references: Maximum number of references used
            cross_reference_result: Optional cross-reference analysis result
            cross_reference_meta: Optional cross-reference metadata
            
        Returns:
            Complete analysis result dictionary
        """
        # Format the publication date
        formatted_publish_date = format_date_for_display(metadata.get('publishDate', ''))
        
        result = {
            'url': url,
            'article': {
                'headline': metadata.get('headline', ''),
                'author': metadata.get('author', ''),
                'publishDate': formatted_publish_date,
                'claims': getattr(article_analysis, 'claims', []),
                'summary': getattr(article_analysis, 'summary', '')
            },
            'reference_processing': processed_references,
            'max_references_used': max_references
        }
        
        # Add cross-reference results if available
        if cross_reference_result:
            result['cross_reference'] = {
                'isMisleading': getattr(cross_reference_result, 'isMisleading', None),
                'reasons': getattr(cross_reference_result, 'reasons', []),
                'explanation': getattr(cross_reference_result, 'explanation', ''),
                'confidence': getattr(cross_reference_result, 'confidence', None)
            }
            
            if cross_reference_meta:
                result['cross_reference_meta'] = cross_reference_meta
        
        return result

    async def analyse_article(self, url: str, max_references: int = 3, days_old: int = 7):
        """
        Analyse a news article with cross-referencing
        
        Args:
            url: The URL of the article to analyse
            max_references: Maximum number of reference sources to use
            days_old: Maximum age of reference articles in days
        """
        try:
            self.logger.info(f"Analysing article from {url} with max_references={max_references}")
            
            # Get the article content using the scraping pipeline
            update_status("Scraping article content", 5, "Web Scraping", 1)
            content = self.scraping_controller.scrape_content(url)
            if not content:
                self.logger.error(f"Failed to scrape article content from {url}")
                update_status("Failed to scrape article content", 25, "Error", -1)
                return None
                
            # Initialise metadata dictionary
            metadata = {
                'headline': '',
                'author': '',
                'publishDate': ''
            }
                
            # Merge metadata from scraper with empty metadata
            # This is just to ensure that the metadata is not empty
            self._merge_metadata(metadata, content)
            
            update_status("Processing main article content", 15, "Article Analysis", 2)
            update_status("Cleaning article text", 17, "Text Processing", 2)
            
            # Process the main article text 
            article_analysis = await self.process_article(content['text'], is_main_article=True)
            
            if not article_analysis:
                self.logger.error("Failed to analyse main article")
                update_status("Failed to analyse main article content", 35, "Error", -1)
                return None
            
            # Report successful article analysis 
            claims_count = len(getattr(article_analysis, 'claims', []))
            update_status(f"Extracted {claims_count} claims from article", 30, "Claims Extraction", 2)
            update_status("Generated article summary", 35, "Summary Generation", 2)
            
            # Search for reference articles using the pipeline
            headline = metadata.get('headline', '')
            query = self.get_search_query(headline)
            
            update_status(f"Generating search query from headline", 38, "Reference Search", 3)
            update_status(f"Searching for reference articles (max: {max_references})", 40, "Reference Search", 3)

            self.logger.info(f"Searching for reference articles with query: {query}, max_references={max_references}")
            reference_results = self.scraping_controller.search_for_articles(
                query=query, 
                original_url=url,
                num_results=max_references,
                days_old=days_old,
                publish_date=metadata.get('publishDate')
            )
            
            self.logger.info(f"Found {len(reference_results)} reference articles to process")
            update_status(f"Found {len(reference_results)} reference articles", 50, "Reference Search", 3)

            # If no reference articles found, flag as potentially misleading
            if len(reference_results) == 0:
                self.logger.warning("No reference articles found - flagging as potentially misleading")
                update_status("No other sources reporting this story", 80, "Cross-Reference", 5)
                
                # Create a synthetic misleading analysis result
                cross_reference_result = type('MisleadingAnalysisSynthetic', (), {
                    'isMisleading': True,
                    'reasons': ["No corroborating sources found"],
                    'explanation': "We couldn't find any other reputable news sources reporting on this story. This could indicate that the information is not widely verified or accepted, which raises concerns about its accuracy. Consider seeking additional verification before accepting the claims in this article.",
                    'confidence': 0.8
                })()
                
                # Skip reference processing and go to final result
                processed_references = {
                    "successful": [],
                    "skipped": []
                }
                
                update_status("Preparing final analysis", 90, "Completion", 6)
                update_status("Finalizing analysis results", 95, "Completion", 6)
                
                # Build and return the final result with our synthetic cross-reference
                return self._build_analysis_result(
                    url=url,
                    article_analysis=article_analysis,
                    metadata=metadata,
                    processed_references=processed_references,
                    max_references=max_references,
                    cross_reference_result=cross_reference_result,
                    cross_reference_meta={"refCount": 0}
                )
                
            main_url = normalise_url(url) if url else ""
            update_status("Processing reference articles", 60, "Reference Analysis", 4)

            # Process reference articles
            processed_references, reference_analyses = await self.process_reference_articles(reference_results, main_url)
            
            cross_reference_result = None
            cross_reference_meta = None
            if reference_analyses:
                update_status(f"Preparing to cross-reference with {len(reference_analyses)} sources", 75, "Cross-Reference", 5)
                update_status(f"Cross-referencing main article with {len(reference_analyses)} sources", 80, "Cross-Reference", 5)

                # Cross-reference the articles
                self.logger.info(f"Cross-referencing article with {len(reference_analyses)} reference articles")
                cross_reference_result, cross_reference_meta = await self.cross_reference_articles(
                    (article_analysis, metadata),
                    reference_analyses
                )
                
                # Report if cross-reference was successful
                if cross_reference_result:
                    is_misleading = getattr(cross_reference_result, 'isMisleading', None)
                    if is_misleading is True:
                        update_status("Potential misleading content detected", 85, "Cross-Reference", 5)
                    elif is_misleading is False:
                        update_status("No misleading content detected", 85, "Cross-Reference", 5)
                    else:
                        update_status("Cross-reference analysis complete", 85, "Cross-Reference", 5)
            
            update_status("Preparing final analysis", 90, "Completion", 6)
            update_status("Finalizing analysis results", 95, "Completion", 6)
                
            # Build and return the final result
            return self._build_analysis_result(
                url=url,
                article_analysis=article_analysis,
                metadata=metadata,
                processed_references=processed_references,
                max_references=max_references,
                cross_reference_result=cross_reference_result,
                cross_reference_meta=cross_reference_meta
            )
                
        except Exception as e:
            self.logger.error(f"Error analysing article: {str(e)}")
            self.logger.debug(f"Exception details: {str(e)}", exc_info=True)
            update_status(f"Error: {str(e)[:100]}", 100, "Error", -1)
            return None

    def _merge_metadata(self, metadata, content):
        """
        Merge metadata from different sources, with priority to existing values
        
        Args:
            metadata: Target metadata dictionary to update
            content: Source content with metadata to merge
        """
        if not metadata.get('headline') and content.get('headline'):
            metadata['headline'] = content['headline']
        if not metadata.get('author') and content.get('author'):
            metadata['author'] = content['author']
        if not metadata.get('publishDate') and content.get('publishDate'):
            metadata['publishDate'] = content['publishDate']
