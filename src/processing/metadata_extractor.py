"""
Metadata extraction module for news articles.

This module implements a multi-layered approach to metadata extraction:
1. Primary: HTML-based extraction from structured elements
2. Secondary: Text-based extraction using regex patterns
3. Tertiary: NER-based extraction as a fallback method

The module handles extracting headline, author, and publication date from
various news article formats, with graceful degradation when optimal
extraction methods fail.
"""

import json
import re
import spacy
from bs4 import BeautifulSoup
from typing import Dict, Optional

from src.utils.logging_utils import get_logger
from src.utils.text_utils import extract_domain, clean_title_from_headline
from src.processing.text_cleaner import TextCleaner

class MetadataExtractor:
    """Extracts metadata from news articles using a multi-layered approach."""
    
    # Constants for headline extraction
    MIN_HEADLINE_WORDS = 3
    MAX_HEADLINE_WORDS = 15
    HEADLINE_CAPITALISATION_THRESHOLD = 0.7
    
    def __init__(self, logger=None):
        """
        Initialise the metadata extractor.
        
        Args:
            logger: Optional logger instance. If not provided, will create a new one.
        """
        # Configure logging
        self.logger = logger or get_logger(__name__)
        
        # Lazy loading for NLP model
        self._nlp = None
        self.text_cleaner = TextCleaner()
        
    @property
    def nlp(self):
        """Lazy loading of spaCy NLP model"""
        if self._nlp is None:
            self.logger.info("Loading spaCy model for NER extraction")
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except:
                self.logger.error("Failed to load spaCy model")
                self._nlp = False  # False to indicate loading failed
        return self._nlp if self._nlp else None
    
    def extract_metadata(self, soup: BeautifulSoup, url: str, content: Optional[Dict] = None) -> Dict:
        """
        Extract metadata using the multi-layered approach.
        
        Args:
            soup: BeautifulSoup object containing the parsed HTML
            url: URL of the article
            content: Optional dictionary containing already extracted content
            
        Returns:
            Dictionary containing extracted metadata
        """
        # Initialise content dict if not provided
        if content is None:
            content = {}
            
        # Initialise basic metadata fields if not present
        if "url" not in content:
            content["url"] = url
        if "domain" not in content:
            domain = extract_domain(url)
            content["domain"] = domain
        
        # Ensure all required metadata fields exist
        for field in ["headline", "author", "publishDate"]:
            if field not in content:
                content[field] = ""
                
        # Primary extraction: HTML-based methods
        self._extract_headline(soup, content)
        self._extract_author(soup, content)
        self._extract_publication_date(soup, content)
        
        # If primary extraction failed for any field, try NER as fallback
        missing_fields = []
        if not content.get('headline'):
            missing_fields.append('headline')
        if not content.get('author'):
            missing_fields.append('author')
        if not content.get('publishDate'):
            missing_fields.append('publishDate')
            
        if len(missing_fields) > 0:
            self.logger.info(f"Primary extraction failed for: {', '.join(missing_fields)}. Using NER fallback")
            # Extract text for NER processing (only once)
            text_for_ner = self._extract_text_for_ner(soup)
            
            # Only process with NER if we have text and the NLP model
            if text_for_ner and self.nlp:
                doc = self.nlp(text_for_ner)
                
                # Apply NER fallback for each missing field
                if 'headline' in missing_fields:
                    self._extract_headline_with_ner(doc, text_for_ner, content)
                if 'author' in missing_fields:
                    self._extract_author_with_ner(doc, text_for_ner, content)
                if 'publishDate' in missing_fields:
                    self._extract_date_with_ner(doc, text_for_ner, content)
            
        return content
    
    def _extract_text_for_ner(self, soup: BeautifulSoup) -> str:
        """Extract text from the document that's most relevant for NER processing"""
        # Extract text from the first few paragraphs where metadata is likely to appear
        first_paragraphs = []
        for p in soup.find_all('p', limit=5):
            if len(p.text.strip()) > 10:  # Skip very short paragraphs
                first_paragraphs.append(p.text.strip())
                
        # Also check header elements
        for header in soup.find_all(['header', 'div'], class_=lambda c: c and any(t in str(c).lower() for t in ['header', 'meta', 'info']) if c else False, limit=2):
            header_text = header.text.strip()
            if header_text:
                first_paragraphs.append(header_text)
                
        return " ".join(first_paragraphs) if first_paragraphs else ""
    
    def _extract_headline(self, soup: BeautifulSoup, content: Dict) -> None:
        """Extract article headline using multiple strategies"""
        # Skip if headline already found
        if content.get('headline'):
            return

        # 1. Check for structured data (Schema.org)
        schema_data = self._extract_schema_org_data(soup)
        if schema_data:
            headline = self._get_headline_from_schema(schema_data)
            if headline:
                content['headline'] = headline
                self.logger.info(f"Found headline in schema.org data: {content['headline'][:50]}...")
                return
        
        # 2. Look for common metadata tags
        for meta_tag in [
            soup.find('meta', property='og:title'),
            soup.find('meta', attrs={'name': 'twitter:title'}),
            soup.find('meta', attrs={'name': 'title'}),
            soup.find('meta', attrs={'name': 'og:title'}),
            soup.find('meta', attrs={'property': 'twitter:title'}),
            soup.find('meta', attrs={'name': 'cXenseParse:author'})
        ]:
            if meta_tag and meta_tag.get('content'):
                content['headline'] = meta_tag.get('content').strip()
                self.logger.info(f"Found headline in meta tag: {content['headline'][:50]}...")
                return
        
        # 3. Try common heading elements with article/headline classes
        for selector in [
            'h1.headline', 'h1.article-title', 'h1.entry-title', 'h1.post-title', 
            '.article_title', '.headline', '.article-headline', '.post-headline',
            'header h1', 'article h1', '.article_header h1', '.article-header h1',
            'h1[itemprop="headline"]', 'h1[class*="title"]', 'h1[class*="headline"]',
            '.article-title', '.story-title', '.post-title', '[data-testid="headline"]'
        ]:
            title_elem = soup.select_one(selector)
            if title_elem:
                content['headline'] = title_elem.text.strip()
                self.logger.info(f"Found headline using selector '{selector}': {content['headline'][:50]}...")
                return
        
        # 4. Default to any h1
        title_tag = soup.find('h1')
        if title_tag:
            content['headline'] = title_tag.text.strip()
            self.logger.info(f"Found headline using default h1: {content['headline'][:50]}...")
            return
        
        # 5. Try article header
        header = soup.find(['header', 'div'], class_=lambda c: c and any(x in c.lower() for x in ['headline', 'title', 'header']) if c else False)
        if header:
            h_tag = header.find(['h1', 'h2'])
            if h_tag:
                content['headline'] = h_tag.text.strip()
                self.logger.info(f"Found headline in article header: {content['headline'][:50]}...")
                return
                
        # 6. Fallback to title tag
        title = soup.find('title')
        if title:
            # Use the shared headline cleaning function from text_utils
            title_text = title.text.strip()
            content['headline'] = clean_title_from_headline(title_text)
            self.logger.info(f"Found headline using page title: {content['headline'][:50]}...")
            return
            
        self.logger.info("Failed to extract headline")

    def _extract_author(self, soup: BeautifulSoup, content: Dict) -> None:
        """Extract article author using multiple strategies"""
        # Skip if author already found
        if content.get('author'):
            return
            
        # 1. Check for structured data (Schema.org)
        schema_data = self._extract_schema_org_data(soup)
        if schema_data:
            author = self._get_author_from_schema(schema_data)
            if author:
                content['author'] = author
                self.logger.info(f"Found author in schema.org data: {author}")
                return
                
        # 2. Look for common metadata tags
        for meta_tag in [
            soup.find('meta', property='author'),
            soup.find('meta', property='article:author'),
            soup.find('meta', attrs={'name': 'author'}),
            soup.find('meta', attrs={'name': 'article:author'}),
            soup.find('meta', attrs={'name': 'twitter:creator'}),
            soup.find('meta', attrs={'property': 'twitter:creator'}),
            soup.find('meta', attrs={'name': 'cXenseParse:author'}),
            soup.find('meta', property='cXenseParse:author'),
            soup.find('meta', attrs={'name': 'twitter:data1'}),
            soup.find('meta', attrs={'name': 'parsely-author'}),
            soup.find('meta', property='parsely-author'),
            soup.find('meta', attrs={'name': 'sailthru.author'}),
            soup.find('meta', property='sailthru.author'),
            soup.find('meta', attrs={'name': 'yahoo-author'}),
            soup.find('meta', property='yahoo-author')
        ]:
            if meta_tag and meta_tag.get('content'):
                author = meta_tag.get('content').strip()
                if author and author.lower() not in ['admin', 'administrator', 'staff', 'guest', 'anonymous']:
                    content['author'] = author
                    self.logger.info(f"Found author in meta tag: {author}")
                    return
                    
        # 3. Try common author elements by class/id/rel
        for selector in [
            '[rel="author"]', '.author', '.byline', '.article-author', 
            '#author', '[itemprop="author"]', '.article__byline', 
            '.c-byline__author', '.entry-author', '.post-author',
            'p.byline', '.story-meta .byline', '.metadata .byline',
            '.article-meta .author', '.article-info .author', 
            '.author-name', '.auth-name', '.authorInfo', '.news-byline',
            '.caas-attr-provider', '.caas-author', '.publisher-anchor', 
            '.author-header', '.author-byline', '.authorName',
            '.article-byline__name', '.article__meta-author',
            '.news-article-provider', '.article-source-author',
            '.entry-meta-author', '.widget__contributor',
            '.author-bio__name', '.contributor-bio'
        ]:
            author_elem = soup.select_one(selector)
            if author_elem:
                # Check if nested element contains actual name (common pattern)
                nested_name = author_elem.select_one('[itemprop="name"]')
                if nested_name:
                    author = nested_name.text.strip()
                else:
                    author = author_elem.text.strip()
                    
                # Clean up author text
                author = self.text_cleaner.clean_author_text(author)
                if author:
                    content['author'] = author
                    self.logger.info(f"Found author using selector '{selector}': {author}")
                    return
                    
        # 4. Try to find author patterns in text with regex
        # Common patterns like "By Author Name", "AUTHOR: Author Name", etc.
        author_patterns = [
            r"[Bb]y\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})",  # By John Smith
            r"[Aa]uthor[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})",  # Author: John Smith
            r"[Ww]ritten\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})",  # Written by John Smith
            r"[Rr]eported\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})",  # Reported by John Smith
            r"[Ee]dited\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})",  # Edited by John Smith
            r"[Ff]rom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})"  # From John Smith
        ]
        
        # Try to find in first few paragraphs
        first_paras = soup.find_all('p', limit=5)
        for p in first_paras:
            p_text = p.text.strip()
            for pattern in author_patterns:
                match = re.search(pattern, p_text)
                if match:
                    author = match.group(1).strip()
                    if author:
                        content['author'] = author
                        self.logger.info(f"Found author using regex pattern: {author}")
                        return
                        
        # 5. Try footer/attribution section
        attribution_section = None
        for selector in ['.attribution', '.footer', '.article-footer', '.content-info', '.meta']:
            section = soup.select_one(selector)
            if section:
                attribution_section = section
                break
                
        if attribution_section:
            attribution_text = attribution_section.text[:200]  # Only check beginning
            # Look for author patterns
            for pattern in author_patterns:
                match = re.search(pattern, attribution_text)
                if match:
                    author = match.group(1).strip()
                    if author:
                        content['author'] = author
                        self.logger.info(f"Found author in attribution section: {author}")
                        return

        self.logger.info("Failed to extract author")
        
    def _extract_publication_date(self, soup: BeautifulSoup, content: Dict) -> None:
        """Extract article publication date using multiple strategies"""
        # Skip if date already found
        if content.get('publishDate'):
            return
            
        # 1. Check for structured data (Schema.org)
        schema_data = self._extract_schema_org_data(soup)
        if schema_data:
            date = self._get_date_from_schema(schema_data)
            if date:
                content['publishDate'] = date
                self.logger.info(f"Found date in schema.org data: {date}")
                return
                
        # 2. Look for common metadata tags
        for meta_tag in [
            soup.find('meta', property='article:published_time'),
            soup.find('meta', attrs={'name': 'article:published_time'}),
            soup.find('meta', property='article:modified_time'),
            soup.find('meta', attrs={'name': 'article:modified_time'}),
            soup.find('meta', property='og:published_time'),
            soup.find('meta', attrs={'name': 'pubdate'}),
            soup.find('meta', attrs={'itemprop': 'datePublished'}),
            soup.find('meta', attrs={'itemprop': 'dateModified'}),
            soup.find('meta', attrs={'name': 'cXenseParse:date'}),
            soup.find('meta', attrs={'name': 'sailthru.date'})
        ]:
            if meta_tag and meta_tag.get('content'):
                date = meta_tag.get('content').strip()
                if date:
                    content['publishDate'] = date
                    self.logger.info(f"Found date in meta tag: {date}")
                    return
                    
        # 3. Look for <time> elements
        for time_tag in soup.find_all('time'):
            if time_tag.get('datetime'):
                date = time_tag.get('datetime').strip()
                if date:
                    content['publishDate'] = date
                    self.logger.info(f"Found date in time element: {date}")
                    return
                    
        # 4. Try common date containers by class/id
        for selector in [
            '.date', '.published', '.article-date', '.post-date', 
            '.publish-date', '.timeago', '.timestamp', '.article__date',
            '.entry-date', '.meta-date', '.article-datetime', '.article_date',
            '[itemprop="datePublished"]', '.modified-date', '.page-date'
        ]:
            date_elem = soup.select_one(selector)
            if date_elem:
                # Check if it's a time element with datetime attribute
                if date_elem.name == 'time' and date_elem.get('datetime'):
                    # If so we can just use the datetime attribute
                    date = date_elem.get('datetime').strip()
                else:
                    # Otherwise we need to extract the text
                    date = date_elem.text.strip()
                    
                # Clean up date text - might contain "Published: " or "Updated: "
                date = self._clean_date_text(date)
                if date:
                    content['publishDate'] = date
                    self.logger.info(f"Found date using selector '{selector}': {date}")
                    return
                    
        # 5. Try to find date patterns in text with regex
        date_patterns = [
            # ISO format
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',
            # Common date formats with year
            r'(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
            r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',
            r'(?:\d{1,2}/\d{1,2}/\d{4})',
            r'(?:\d{1,2}\.\d{1,2}\.\d{4})'
        ]
        
        # Try to find in first few paragraphs or header section
        for elem in soup.find_all(['p', 'div', 'span'], class_=lambda c: c and any(t in str(c).lower() for t in ['date', 'time', 'published', 'modified']) if c else False, limit=5):
            elem_text = elem.text.strip()
            for pattern in date_patterns:
                match = re.search(pattern, elem_text)
                if match:
                    date = match.group(0).strip()
                    if date:
                        content['publishDate'] = date
                        self.logger.info(f"Found date using regex pattern: {date}")
                        return
                        
        self.logger.info("Failed to extract publication date")
        return

    def _extract_schema_org_data(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract structured data from Schema.org JSON-LD"""
        if not soup:
            return None
            
        schema = soup.find('script', type='application/ld+json')
        if not schema:
            return None
            
        try:
            data = json.loads(schema.string)
            return data
        except json.JSONDecodeError:
            self.logger.warning("Error parsing JSON-LD schema")
            return None
        except Exception as e:
            self.logger.warning(f"Unexpected error extracting schema data: {str(e)}")
            return None
            
    def _get_headline_from_schema(self, data) -> Optional[str]:
        """Extract headline from Schema.org data"""
        if not data:
            return None
            
        try:
            # Handle both single objects and arrays of objects
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('headline'):
                        return item['headline']
            elif isinstance(data, dict):
                if data.get('headline'):
                    return data['headline']
                # Also check for nested objects
                if data.get('@type') == 'BreadcrumbList' and data.get('itemListElement'):
                    for item in data['itemListElement']:
                        if item.get('name'):
                            return item['name']
        except Exception as e:
            self.logger.warning(f"Error extracting headline from schema: {str(e)}")
            
        return None
        
    def _get_author_from_schema(self, data) -> Optional[str]:
        """Extract author from Schema.org data"""
        if not data:
            return None
            
        try:
            # Handle both single objects and arrays of objects
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        author = None
                        # Check different author formats
                        if item.get('author'):
                            author = item['author']
                        elif item.get('creator'):
                            author = item['creator']
                            
                        # Author can be string or object
                        if isinstance(author, str):
                            return author
                        elif isinstance(author, dict) and author.get('name'):
                            return author['name']
                        elif isinstance(author, list) and author and isinstance(author[0], dict) and author[0].get('name'):
                            return author[0]['name']
                            
            elif isinstance(data, dict):
                author = None
                # Check different author formats
                if data.get('author'):
                    author = data['author']
                elif data.get('creator'):
                    author = data['creator']
                
                # Author can be string or object
                if isinstance(author, str):
                    return author
                elif isinstance(author, dict) and author.get('name'):
                    return author['name']
                elif isinstance(author, list) and author and isinstance(author[0], dict) and author[0].get('name'):
                    return author[0]['name']
        except Exception as e:
            self.logger.warning(f"Error extracting author from schema: {str(e)}")
            
        return None
        
    def _get_date_from_schema(self, data) -> Optional[str]:
        """Extract publication date from Schema.org data"""
        if not data:
            return None
            
        try:
            date_fields = ['datePublished', 'dateCreated', 'publishedDate', 'dateModified']
            
            # Handle both single objects and arrays of objects
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Check different date formats
                        for date_field in date_fields:
                            if item.get(date_field):
                                return item[date_field]
            elif isinstance(data, dict):
                # Check different date formats
                for date_field in date_fields:
                    if data.get(date_field):
                        return data[date_field]
        except Exception as e:
            self.logger.warning(f"Error extracting date from schema: {str(e)}")
            
        return None
        
    def _clean_date_text(self, text: str) -> str:
        """Clean up date text by removing common prefixes"""
        # Use TextCleaner's implementation
        return self.text_cleaner.clean_date_text(text)

    def _extract_author_with_ner(self, doc: spacy.tokens.Doc, text_for_ner: str, content: Dict) -> None:
        """Extract author using NER"""
        # Look for PERSON entities that might be authors
        person_entities = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        
        # Filter out likely non-authors (common names in news articles)
        if person_entities:
            non_authors = [
                "joe biden", "donald trump", "vladimir putin", "xi jinping", 
                "kamala harris", "emmanuel macron", "rishi sunak", "olaf scholz",
                "justin trudeau", "anthony albanese", "michael gove", "keir starmer"
            ]
            filtered_persons = [p for p in person_entities if p.lower() not in non_authors]
            
            if filtered_persons:
                # Prioritize entities that appear near byline keywords
                byline_keywords = ["by", "written", "reporter", "correspondent", "journalist", "author"]
                for person in filtered_persons:
                    # Check if person appears near a byline keyword
                    for keyword in byline_keywords:
                        if f"{keyword} {person.lower()}" in text_for_ner.lower() or f"{person} is {keyword}" in text_for_ner.lower():
                            author = self.text_cleaner.clean_author_text(person)
                            if author:
                                content['author'] = author
                                self.logger.info(f"Found author using NER with byline context: {author}")
                                return
                        
                # If still no author, take the first person entity as fallback
                author = self.text_cleaner.clean_author_text(filtered_persons[0])
                if author:
                    content['author'] = author
                    self.logger.info(f"Found author using NER: {author}")
                        
    def _extract_date_with_ner(self, doc: spacy.tokens.Doc, text_for_ner: str, content: Dict) -> None:
        """Extract publication date using NER"""
        # Use the DATE entities from spaCy
        date_entities = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
        
        if date_entities:
            # Filter for likely publication dates (usually contain year)
            for date in date_entities:
                # Check if the date string contains a year pattern
                if re.search(r'(20\d\d|19\d\d)', date):
                    # Check for likely publication date context
                    date_context_words = ["published", "posted", "updated", "date", "written"]
                    
                    # Look for dates with context
                    for context_word in date_context_words:
                        if (f"{context_word} {date.lower()}" in text_for_ner.lower() or 
                            f"{context_word}: {date.lower()}" in text_for_ner.lower()):
                            content['publishDate'] = date
                            self.logger.info(f"Found publication date using NER with context: {date}")
                            return
                    
                    # If no date with perfect context, just use the first valid date
                    if not content.get('publishDate'):
                        content['publishDate'] = date
                        self.logger.info(f"Found publication date using NER: {date}")
                        return
                        
    def _extract_headline_with_ner(self, doc: spacy.tokens.Doc, text_for_ner: str, content: Dict) -> None:
        """Extract headline using NER and text patterns"""
        # Get sentences from the spaCy document
        sentences = [sent.text.strip() for sent in doc.sents]
        
        if not sentences:
            return
            
        # First look for sentences that appear before bylines
        for i, sentence in enumerate(sentences):
            words = sentence.split()
            if self.MIN_HEADLINE_WORDS <= len(words) <= self.MAX_HEADLINE_WORDS:
                # Check if next sentence contains byline
                if i < len(sentences) - 1 and re.search(r'[Bb]y\s+[A-Z][a-z]+', sentences[i+1]):
                    content['headline'] = sentence
                    self.logger.info(f"Found headline before byline: {sentence}")
                    return
        
        # If no headline found, try capitalisation pattern (headlines often have most words capitalized)
        for sentence in sentences:
            words = sentence.split()
            if self.MIN_HEADLINE_WORDS <= len(words) <= self.MAX_HEADLINE_WORDS and sum(1 for w in words if w[0].isupper()) / len(words) > self.HEADLINE_CAPITALISATION_THRESHOLD:
                content['headline'] = sentence
                self.logger.info(f"Found headline using NER text patterns: {sentence}")
                return 