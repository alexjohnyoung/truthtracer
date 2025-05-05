"""
Text utility functions for processing article content.

This module provides utilities for normalising URLs and other text processing tasks.
"""

import re
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs

def normalise_url(url: str) -> str:
    """
    Normalise a URL by removing common tracking parameters and fragments
    
    Args:
        url: URL to normalise
        
    Returns:
        Normalised URL
    """
    if not url:
        return ""
        
    # Remove URL fragments (everything after #)
    url = url.split('#')[0]
    
    # Remove common tracking parameters
    tracking_params = [
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'ref', 'ref_src', 'ref_url', 'source', 'source_id'
    ]
    
    # Split URL into base and query
    if '?' in url:
        base_url, query = url.split('?', 1)
        params = query.split('&')
        filtered_params = []
        
        for param in params:
            if '=' in param:
                param_name, param_value = param.split('=', 1)
                if param_name.lower() not in tracking_params:
                    filtered_params.append(param)
            else:
                filtered_params.append(param)
                
        if filtered_params:
            url = base_url + '?' + '&'.join(filtered_params)
        else:
            url = base_url
    
    # Remove trailing slash
    if url.endswith('/'):
        url = url[:-1]
        
    return url

def extract_domain(url: str, remove_www: bool = True) -> str:
    """
    Extract domain from URL
    
    Args:
        url: The URL to extract domain from
        remove_www: Whether to remove 'www.' prefix from domain
        
    Returns:
        Domain name
    """
    if not url:
        return ""
        
    try:
        domain = urlparse(url).netloc.lower()
        if remove_www and domain.startswith('www.'):
            domain = domain[4:]  # Remove www. prefix
        return domain
    except:
        return ""

def extract_url_from_redirect(redirect_url: str) -> str:
    """
    Extract the target URL from a Google redirect URL
    
    Args:
        redirect_url: Google redirect URL (e.g., "/url?q=https://example.com")
        
    Returns:
        Target URL or original URL if not a redirect
    """
    if not redirect_url:
        return ""
        
    try:
        # Handle Google redirect URLs
        if redirect_url.startswith('/url?') or 'google.com/url' in redirect_url:
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)
            
            if 'url' in query_params:
                return query_params['url'][0]
            elif 'q' in query_params:
                return query_params['q'][0]
        
        # Not a redirect URL
        return redirect_url
    except:
        return redirect_url

def clean_title_from_headline(title_text: str) -> str:
    """Clean up a title text to extract just the headline
    
    Args:
        title_text: Raw title text that might contain site name
        
    Returns:
        str: Cleaned headline
    """
    if not title_text:
        return ""
        
    title_text = title_text.strip()
    
    # Try to remove site name if separated by | or -
    if ' | ' in title_text:
        return title_text.split(' | ')[0].strip()
    elif ' - ' in title_text:
        return title_text.split(' - ')[0].strip()
    else:
        return title_text 