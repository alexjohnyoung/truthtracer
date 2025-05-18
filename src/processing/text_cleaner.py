import re
import os
from baml_client.async_client import b
from src.utils.logging_utils import get_logger


class TextCleaner:
    """
    A utility class for cleaning and normalising web page content text.
    Provides methods to remove noise, normalise whitespace, and structure
    paragraphs appropriately.
    """
    
    def __init__(self):
        """Initialise the text cleaner with common patterns"""
        # Configure logging
        self.logger = get_logger(__name__)
        
        # Regex patterns for noise removal
        self.email_pattern = re.compile(r'\S+@\S+\.\S+')
        self.url_pattern = re.compile(r'https?://\S+')
        self.cookie_pattern = re.compile(r'(?i)we use cookies to.*?(?:privacy|experience|setting|service)')
        self.cookie_pattern2 = re.compile(r'(?i)this site uses cookies.*?(?:privacy|experience|setting|service)')
        self.copyright_pattern = re.compile(r'(?i)©.*?rights reserved\.?')
        self.copyright_pattern2 = re.compile(r'(?i)copyright ©.*?20\d\d')
        self.social_pattern = re.compile(r'(?i)follow us on.*?(?:twitter|facebook|instagram|linkedin)')
        self.share_pattern = re.compile(r'(?i)share this.*?(?:article|story|post)')
        self.subscribe_pattern = re.compile(r'(?i)subscribe to our newsletter')
        self.signup_pattern = re.compile(r'(?i)sign up for our.*?newsletter')
        self.subscribe_pattern2 = re.compile(r'(?i)subscribe for.*?(?:free|email|newsletter)')
        self.navigation_pattern = re.compile(r'(?i)menu|home|about us|contact|search')
        self.ad_pattern = re.compile(r'(?i)advertisement|sponsored|promoted content')
        
    def clean_content(self, text: str) -> str:
        """
        Clean extracted content to remove noise and normalise formatting
        
        Args:
            text: Raw text content to clean
            
        Returns:
            Cleaned and normalised text content
        """
        if not text:
            return ""
            
        # Convert to string if not already
        text = str(text)
        
        # Remove excessive whitespace and normalise
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove email addresses (common in footers)
        text = self.email_pattern.sub('', text)
        
        # Remove URLs
        text = self.url_pattern.sub('', text)
        
        # Remove common cookie/privacy notice text
        text = self.cookie_pattern.sub('', text)
        text = self.cookie_pattern2.sub('', text)
        
        # Remove copyright notices
        text = self.copyright_pattern.sub('', text)
        text = self.copyright_pattern2.sub('', text)
        
        # Remove social media prompts
        text = self.social_pattern.sub('', text)
        text = self.share_pattern.sub('', text)
        
        # Remove subscription/newsletter prompts
        text = self.subscribe_pattern.sub('', text)
        text = self.signup_pattern.sub('', text)
        text = self.subscribe_pattern2.sub('', text)
        
        # Remove common navigation text
        text = self.navigation_pattern.sub('', text)
        
        # Remove advertising text
        text = self.ad_pattern.sub('', text)
        
        # Re-normalise whitespace after all removals
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Split into paragraphs - any 2+ newlines are paragraph breaks
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Filter out short paragraphs (likely menu items, footer text, etc.)
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 40]
        
        # Rejoin using proper paragraph formatting
        text = '\n\n'.join(paragraphs)
        
        return text
        
    def clean_author_text(self, text: str) -> str:
        """
        Clean up author text by removing common prefixes and suffixes
        
        Args:
            text: Raw author text to clean
            
        Returns:
            Cleaned author text
        """
        if not text:
            return ""
            
        # Convert to string if not already
        text = str(text).strip()
        
        # Remove common prefixes
        prefixes = ['by ', 'BY ', 'By ', 'AUTHOR: ', 'Author: ', 'author: ', 'Written by ', 'written by ',
                   'Reported by ', 'reported by ', 'From ', 'from ', 'Edited by ', 'edited by ']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                
        # Remove positions that sometimes appear after name
        positions = [
            r', Staff Writer$', r', Editor$', r', Reporter$', r', Correspondent$',
            r' - Staff Writer$', r' - Editor$', r' - Reporter$', r' - Correspondent$',
            r', Associated Press$', r', AP$', r', Reuters$', r', AFP$', r', Bloomberg$',
            r' \(AP\)$', r' \(Reuters\)$', r' \(AFP\)$', r' \(Bloomberg\)$',
            r', Staff$', r', Contributors?$', r', Special to.*$', r', Guest Writer$'
        ]
        for position in positions:
            text = re.sub(position, '', text, flags=re.IGNORECASE)
            
        # Remove phrases that sometimes get captured
        phrases_to_remove = [
            'updated at', 'published at', 'updated on', 'published on',
            'minutes ago', 'hours ago', 'days ago', 'all rights reserved',
            'copyright', 'contributor', 'exclusive to'
        ]
        for phrase in phrases_to_remove:
            if phrase in text.lower():
                parts = text.lower().split(phrase)
                text = parts[0].strip()
            
        return text.strip()
    
    
    def clean_date_text(self, text: str) -> str:
        """
        Clean up date text by removing common prefixes
        
        Args:
            text: Raw date text to clean
            
        Returns:
            Cleaned date text
        """
        if not text:
            return ""
            
        # Convert to string if not already
        text = str(text).strip()
        
        # Remove common prefixes
        prefixes = ['Published: ', 'Published ', 'PUBLISHED: ', 'Updated: ', 'Updated ', 'UPDATED: ']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                
        return text.strip()
        
    @staticmethod
    async def clean_article_with_llm(text: str) -> str:
        """
        Clean article text using LLM to remove noise
        
        Args:
            text: Raw article text
            
        Returns:
            Cleaned article text string
        """
        logger = get_logger(__name__)
        
        if not text or len(text.strip()) == 0:
            return ""
                
        # Check if LLM cleaning should be skipped
        skip_env = os.environ.get('SKIP_LLM_CLEANING', 'false').strip().lower()
        skip_llm_cleaning = skip_env in ('true', '1', 'yes', 't')
        
        if skip_llm_cleaning:
            logger.info(f"Skipping LLM cleaning due to SKIP_LLM_CLEANING={skip_env}")
            return text
                
        # Clean the article text
        try:
            logger.info(f"Using LLM to clean article text of length {len(text)}")
            result = await b.CleanArticleText(text)
            
            if result:
                # Calculate the percentage of text removed
                original_length = len(text)
                cleaned_length = len(result.text)
                removed_percent = ((original_length - cleaned_length) / original_length) * 100 if original_length > 0 else 0
                logger.info(f"LLM cleaning removed {removed_percent:.1f}% of text ({original_length} → {cleaned_length} chars)")
                
                # Return the cleaned text
                return result.text
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in LLM article cleaning: {error_msg}")
            
        # If cleaning fails, return original text
        logger.warning("LLM cleaning failed - using original text")
        return text
        