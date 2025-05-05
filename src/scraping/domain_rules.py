"""
Domain-specific rules and configurations for web scraping.
Planning to add more rules here in the future
"""

class DomainRules:
    # Blocked domains that we don't want to scrape
    BLOCKED_DOMAINS = {
        'msn.com',  
        'msnbc.com', 
        'telegraph.co.uk', 
    }
    
    @classmethod
    def is_blocked(cls, domain):
        """Check if domain is in the blocked list"""
        return any(blocked in domain for blocked in cls.BLOCKED_DOMAINS)