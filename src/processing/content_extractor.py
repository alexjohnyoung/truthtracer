import re
from bs4 import BeautifulSoup
from typing import Dict, List
from src.utils.logging_utils import get_logger
from src.utils.text_utils import extract_domain

class ContentExtractor:
    """
    This module extracts article content from HTML pages using simple
    fallback strategies for different news site layouts.
    """
    
    def __init__(self, logger=None):
        """Initialise with optional logger."""
        self.logger = logger or get_logger(__name__)
        self.article_patterns = [
            'article', 'story', 'post', 'content', 'news', 'body', 'main'
        ]
        self.noise_patterns = [
            'sidebar', 'comment', 'footer', 'header', 'menu', 'nav', 
            'social', 'share', 'related', 'ad', 'popup', 'cookie', 'paywall'
        ]

    def extract_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract article content and metadata from HTML."""
        # Initialise result dictionary
        result = {
            "url": url,
            "domain": extract_domain(url),
            "headline": "",
            "author": "",
            "publishDate": "",
            "text": "",
            "links": []
        }
        
        # Extract content and links
        content = self._extract_with_fallbacks(soup)
        links = self._extract_links(soup, url)
        
        # Update result
        result["text"] = content
        result["links"] = links
        
        self.logger.info(f"Extracted {len(content)} chars from {result['domain']}")
        return result
    
    def _extract_with_fallbacks(self, soup: BeautifulSoup) -> str:
        """Try multiple content extraction strategies in sequence."""
        # Strategy 1: Semantic elements
        content = self._extract_by_semantic_elements(soup)
        if self._is_valid_content(content):
            return content
            
        # Strategy 2: Paragraph collection
        return self._extract_by_paragraphs(soup)
    
    def _is_valid_content(self, content: str, min_length: int = 300) -> bool:
        """Check if content is valid and long enough."""
        return bool(content and len(content) >= min_length)
    
    def _extract_by_semantic_elements(self, soup: BeautifulSoup) -> str:
        """Extract content using semantic HTML elements."""
        semantic_tags = ['article', 'main', '[role="main"]', '[itemprop="articleBody"]']
        
        for tag in semantic_tags:
            elements = soup.select(tag)
            clean_elements = self._filter_noise_elements(elements)
            
            if clean_elements:
                # Sort by length if multiple elements found
                if len(clean_elements) > 1:
                    clean_elements.sort(key=lambda e: len(e.text.strip()), reverse=True)
                
                content = clean_elements[0].text.strip()
                if content:
                    self.logger.debug(f"Found {len(content)} chars using semantic element '{tag}'")
                    return content
        
        return ""
    
    def _extract_by_paragraphs(self, soup: BeautifulSoup) -> str:
        """Extract content by collecting all substantial paragraphs."""
        # Only include paragraphs with substantial content (40+ chars)
        paragraphs = [
            p.text.strip() for p in soup.find_all('p') 
            if len(p.text.strip()) > 40
        ]
        print(f"Found {len(paragraphs)} paragraphs")
        
        if paragraphs:
            content = '\n\n'.join(paragraphs)
            self.logger.debug(f"Found {len(content)} chars from {len(paragraphs)} paragraphs")
            return content
        
        return ""
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract and normalise links from the article."""
        links = []
        try:
            # Extract all anchor tags
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '').strip()
                
                # Skip if empty, javascript link, or anchor link
                if not href or href.startswith(('javascript:', '#', 'mailto:')):
                    continue
                    
                # Get the link text and clean it
                text = a_tag.get_text().strip()
                
                if href and text:
                    links.append({
                        'href': href,
                        'text': text
                    })
        except Exception as e:
            self.logger.error(f"Error extracting links: {e}")
            
        return links
    
    def _filter_noise_elements(self, elements: List) -> List:
        """Remove elements matching noise patterns."""
        return [
            element for element in elements 
            if not self._is_noise_element(element)
        ]
    
    def _is_noise_element(self, element) -> bool:
        """Check if element matches any noise pattern."""
        element_attrs = str(element.get('class', [])) + str(element.get('id', ''))
        return any(
            re.search(pattern, element_attrs, re.IGNORECASE) 
            for pattern in self.noise_patterns
        )