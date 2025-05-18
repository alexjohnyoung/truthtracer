class DomainRules:
    # Blocked domains that we don't want to scrape
    # Usually because of video content
    BLOCKED_DOMAINS = {
        'msn.com',  
        'msnbc.com', 
        'telegraph.co.uk', 
    }
    
    @classmethod
    def is_blocked(cls, domain):
        """Check if domain is in the blocked list"""
        return any(blocked in domain for blocked in cls.BLOCKED_DOMAINS)