"""
Date utility functions for handling dates in articles and searches.

This module provides utilities for date handling, parsing, and determining date ranges
for article searches.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, Union


def get_article_year(publish_date: Optional[str]) -> Optional[int]:
    """
    Extract the year from a publication date string.
    
    Args:
        publish_date: Publication date string
        
    Returns:
        Year as integer, or None if not found
    """
    if not publish_date:
        return None
        
    # Try to extract year using regex
    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', str(publish_date))
    if year_match:
        return int(year_match.group(1))
    
    return None


def parse_article_date(publish_date: Optional[str]) -> Optional[datetime]:
    """
    Parse an article publication date string into a datetime object.
    
    Args:
        publish_date: Publication date string in various formats
        
    Returns:
        datetime object or None if parsing fails
    """
    if not publish_date:
        return None
    
    # Clean the input string
    date_str = publish_date.strip()
    
    # Common date formats to try
    date_formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO 8601: 2022-04-04T17:50:18.000Z
        "%Y-%m-%dT%H:%M:%SZ",     # ISO 8601 without milliseconds
        "%Y-%m-%d",               # 2023-01-01
        "%Y/%m/%d",               # 2023/01/01
        "%m/%d/%Y",               # 01/01/2023
        "%d/%m/%Y",               # 01/01/2023
        "%d %B %Y",               # 11 April 2022
        "%d %b %Y",               # 11 Apr 2022
        "%B %d %Y",               # April 11 2022
        "%b %d %Y",               # Apr 11 2022
        "%B %d, %Y",              # January 1, 2023
        "%b %d, %Y",              # Jan 1, 2023
    ]
    
    # Try exact format matching
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Month name mapping
    month_map = {
        'january': 1, 'jan': 1, 
        'february': 2, 'feb': 2, 
        'march': 3, 'mar': 3, 
        'april': 4, 'apr': 4, 
        'may': 5, 
        'june': 6, 'jun': 6, 
        'july': 7, 'jul': 7, 
        'august': 8, 'aug': 8, 
        'september': 9, 'sep': 9, 
        'october': 10, 'oct': 10, 
        'november': 11, 'nov': 11, 
        'december': 12, 'dec': 12
    }
    
    # Define pattern-specific parsing functions
    def parse_day_month_year(match):
        """Parse dates in format: "11 April 2022" """
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        month = month_map.get(month_name)
        return _create_date(year, month, day)
    
    def parse_month_day_year(match):
        """Parse dates in format: "April 11, 2022" or "April 11 2022" """
        month_name = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3))
        month = month_map.get(month_name)
        return _create_date(year, month, day)
    
    def parse_year_month_day(match):
        """Parse dates in format: "2022-04-11" or "2022/04/11" """
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return _create_date(year, month, day)
    
    def parse_ambiguous_date(match):
        """Parse dates in format: "11/04/2022" or "04/11/2022" (ambiguous MM/DD vs DD/MM) """
        first = int(match.group(1))
        second = int(match.group(2))
        year = int(match.group(3))
        return _try_date_formats(first, second, year)
    
    # Dictionary of regex patterns with corresponding parse functions
    patterns = {
        # Day Month Year: "11 April 2022"
        r'(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})': parse_day_month_year,
        
        # Month Day Year: "April 11, 2022" or "April 11 2022"
        r'([a-zA-Z]+)\s+(\d{1,2})(?:,?)\s+(\d{4})': parse_month_day_year,
        
        # Year-Month-Day: "2022-04-11" or "2022/04/11"
        r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})': parse_year_month_day,
        
        # Day/Month/Year or Month/Day/Year: "11/04/2022" or "04/11/2022"
        r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})': parse_ambiguous_date
    }
    
    # Try each pattern
    for pattern, parser in patterns.items():
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            try:
                result = parser(match)
                if result:
                    return result
            except (ValueError, KeyError):
                continue
    
    # Last resort - extract just the year
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', date_str)
    if year_match:
        try:
            return datetime(int(year_match.group(1)), 1, 1)
        except ValueError:
            pass
    
    return None

def _create_date(year: int, month: Optional[int], day: int) -> Optional[datetime]:
    """Helper function to create a datetime with validation"""
    try:
        if month and 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return datetime(year, month, day)
    except ValueError:
        pass
    return None

def _try_date_formats(first: int, second: int, year: int) -> Optional[datetime]:
    """Try both MM/DD and DD/MM interpretations"""
    # Try MM/DD format
    date = _create_date(year, first, second)
    if date:
        return date
    
    # Try DD/MM format
    return _create_date(year, second, first)


def format_date_for_display(date_str: Optional[str]) -> str:
    """
    Format a date string for display by removing the time component.
    
    Args:
        date_str: Date string in any format
        
    Returns:
        Formatted date string (YYYY-MM-DD) or the original string if parsing fails
    """
    if not date_str:
        return ""
        
    # Check if the date has a 'T' character (ISO format with time)
    if 'T' in date_str:
        # Try to parse and reformat the date
        dt = parse_article_date(date_str)
        if dt:
            # Return just the date part in YYYY-MM-DD format
            return dt.strftime('%Y-%m-%d')
    
    # If no 'T' or parsing fails, return the original string
    return date_str


def calculate_search_date_params(publish_date: Optional[str], days_old: int = 7) -> Dict[str, str]:
    """
    Calculate date parameters for search, using a wider window to find more related articles.
    Uses a window from 7 days before the article's publication date to 30 days after publication.
    
    Args:
        publish_date: Publication date of the article
        days_old: Default time window in days (used if publish_date is not provided)
        
    Returns:
        Dictionary with date parameters for search
    """
    params = {}
    
    # Parse the publication date
    article_date = parse_article_date(publish_date)
    
    if article_date:
        # Check how recent the article is
        now = datetime.now()
        days_since_publication = (now - article_date).days
        
        # For very recent articles (within 7 days), use a wider window
        if days_since_publication <= 7:
            # Start from 14 days before current date to capture most recent news
            start_date = now - timedelta(days=14)
            # End at current date plus 1 day to include everything up to now
            end_date = now + timedelta(days=1)
        else:
            # For older articles, create a window of 14 days before to 30 days after
            start_date = article_date - timedelta(days=14)
            # Calculate end date (30 days after article publication)
            end_date = article_date + timedelta(days=30)
            
        # Format dates as MM/DD/YYYY
        date_min = f"{start_date.month}/{start_date.day}/{start_date.year}"
        date_max = f"{end_date.month}/{end_date.day}/{end_date.year}"
        
        # Set the custom date range parameter
        params['tbs'] = f'cdr:1,cd_min:{date_min},cd_max:{date_max}'
    else:
        # If no publication date available, use a wider default time window
        if days_old <= 1:
            params['tbs'] = 'qdr:w'  # Last week instead of just one day
        elif days_old <= 7:
            params['tbs'] = 'qdr:m1'  # Last month instead of just one week
        elif days_old <= 31:
            params['tbs'] = 'qdr:m3'  # Last 3 months
        else:
            params['tbs'] = 'qdr:y'  # Last year
    
    return params
