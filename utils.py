from datetime import datetime
from urllib.parse import urlparse

COMPANY_MAPPINGS = {
    'subo.se': 'Sundsvalls Bostäder',
    'dios.se': 'Diös Fastigheter',
    # Add more companies here as needed
}

def get_company_name(url: str) -> str:
    """Extract company name from URL using mapping."""
    try:
        domain = urlparse(url).netloc.lower()
        domain = domain.replace('www.', '')
        return COMPANY_MAPPINGS.get(domain, 'Unknown Company')
    except:
        return 'Unknown Company'

def format_notification_title(url: str) -> str:
    """Format the notification title with date and company name."""
    company = get_company_name(url)
    date = datetime.now().strftime('%Y-%m-%d')
    return f"🏠 {company} [{date}]"
