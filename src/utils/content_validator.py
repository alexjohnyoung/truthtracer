"""
Content validation utility for web scraping.

This module provides utilities for validating web page content quality,
determining if a page has meaningful content, and validating extraction results.
"""

import re
from typing import Dict, Optional, List, Tuple
from bs4 import BeautifulSoup


class ContentValidator:
    """
    Utility class for validating web page content and extraction results.
    Centralises content validation logic that was previously scattered across 
    multiple classes.
    """
    
    @staticmethod
    def has_meaningful_content(soup: BeautifulSoup, min_text_length: int = 100) -> bool:
        """
        Powerful function to check if the page has meaningful content that indicates it's a valid news article
        Used for static scraping to determine if we need to use dynamic scraping
        
        Args:
            soup: BeautifulSoup object containing the parsed HTML
            min_text_length: Minimum text length to consider content meaningful
            
        Returns:
            Boolean indicating if meaningful content was found
        """
        if not soup:
            return False
            
        # Check for common content indicators
        content_indicators = [
            # Direct article content
            lambda s: bool(s.find('article') and len(s.find('article').get_text(strip=True)) > min_text_length),
            lambda s: bool(s.find(class_=re.compile(r'article|story|post-content')) and 
                          len(s.find(class_=re.compile(r'article|story|post-content')).get_text(strip=True)) > min_text_length),
            # Main content areas
            lambda s: bool(s.find('main') and len(s.find('main').get_text(strip=True)) > min_text_length),
            lambda s: bool(s.find(id=re.compile(r'content|main')) and 
                          len(s.find(id=re.compile(r'content|main')).get_text(strip=True)) > min_text_length),
            # Multiple paragraphs with substantial text
            lambda s: len([p for p in s.find_all('p') if len(p.get_text(strip=True)) > 50]) >= 2
        ]
        
        # Look for article content with more specific selectors
        article_selectors = [
            'article',
            '.article-body',
            '.story-content',
            '.article-content',
            '[role="article"]',
            '#content-main',
            '.wysiwyg',
            '.article__content',
            '#main-content-area'
        ]
        
        for selector in article_selectors:
            content = soup.select_one(selector)
            if content and len(content.get_text(strip=True)) > min_text_length:
                return True
                
        # If we find any meaningful content from our indicators, it's not a cookie/consent page
        return any(check(soup) for check in content_indicators)
    
    @staticmethod
    def is_blocked_page(soup: BeautifulSoup) -> Tuple[bool, str]:
        """
        Detect if a page is a block/challenge page
        
        Args:
            soup: BeautifulSoup object containing the parsed HTML
            
        Returns:
            Tuple of (is_blocked, reason)
        """
        if not soup:
            return False, ""
            
        # Common block patterns to check
        block_patterns = [
            "sorry, you have been blocked",
            "access denied",
            "cloudflare",
            "403 forbidden",
            "captcha",
            "our systems have detected unusual traffic",
            "please complete the security check",
            "your ip address has been blocked",
            "your browser has been blocked",
            "your request has been blocked"
        ]
        
        page_text = soup.get_text().lower()
        for pattern in block_patterns:
            if pattern in page_text:
                return True, pattern
                
        return False, ""
    
    @staticmethod
    def is_cookie_consent_page(soup: BeautifulSoup) -> bool:
        """
        Determine if a page is primarily a cookie consent page
        
        NOT CURRENTLY USED ANYMORE (Read comments in the pipeline.py file)
        Args:
            soup: BeautifulSoup object containing the parsed HTML
            
        Returns:
            Boolean indicating if the page is a cookie consent page
        """
        if not soup:
            return False
            
        # Common cookie consent keywords
        cookie_terms = [
            'cookie', 'cookies', 'consent', 'gdpr', 'ccpa', 'privacy settings',
            'privacy policy', 'accept cookies', 'cookie policy', 
            'we use cookies', 'this website uses cookies'
        ]
        
        # Get the text of the page
        page_text = soup.get_text().lower()
        
        # Count cookie-related terms
        cookie_term_count = sum(page_text.count(term) for term in cookie_terms)
        
        # If cookie terms appear frequently and page is short, it's likely a consent page
        if cookie_term_count > 3 and len(page_text) < 1000:
            return True
            
        # Look for common cookie consent elements
        consent_elements = [
            soup.find('div', id=lambda x: x and any(term in str(x).lower() for term in ['cookie', 'consent', 'gdpr'])),
            soup.find('div', class_=lambda x: x and any(term in str(x).lower() for term in ['cookie', 'consent', 'gdpr'])),
            soup.find('button', string=lambda x: x and any(term in str(x).lower() for term in ['accept', 'agree', 'allow'])),
            soup.find('div', role='dialog')
        ]
        
        # If any consent elements take up most of the page, it's a consent page
        if any(consent_elements):
            # Get visible text nodes
            main_content = [p.get_text() for p in soup.find_all('p') if len(p.get_text(strip=True)) > 20]
            
            # If there's very little main content but consent elements exist, it's a consent page
            if len(main_content) < 3:
                return True
                
        return False
    