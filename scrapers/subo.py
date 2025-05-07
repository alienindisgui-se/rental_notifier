import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from .base import RentalScraper

class SuboScraper(RentalScraper):
    def __init__(self):
        self.url = "https://www.subo.se/lediga-lagenheter/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def scrape(self, existing_listings):
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            current_addresses = set()
            newly_found = []
            filtered_listings = []
            reactivated = []

            # Extract listings from HTML
            elementor_divs = soup.find_all('div', class_='elementor')
            listing_containers = [item for item in elementor_divs 
                                if item.get('data-elementor-type') == 'jet-listing-items']

            for item in listing_containers:
                url_element = item.find('div', class_='make-column-clickable-elementor')
                url = url_element.get('data-column-clickable') if url_element else None
                h2_elements = item.find_all('h2', class_='elementor-heading-title')

                listing_data = {
                    'address': None,
                    'url': url,
                    'price': None,
                    'rooms': None,
                    'size': None,
                    'available': None,
                    'image_url': None
                }

                # Extract image URL using existing methods
                parent_item = item.find_parent('div', class_='jet-listing-grid__item')
                if parent_item:
                    style_tag = parent_item.find('style')
                    if style_tag and style_tag.string:
                        match = re.search(r'background-image:\s*url\(["\'](.+?)["\']\)', style_tag.string)
                        if match:
                            listing_data['image_url'] = match.group(1)

                # Parse text fields
                for h2 in h2_elements:
                    text = h2.text.strip()
                    if ',' in text and not listing_data['address']:
                        listing_data['address'] = text
                    elif ':-/månad' in text and not listing_data['price']:
                        listing_data['price'] = text
                    elif 'rum' in text and any(char.isdigit() for char in text) and not listing_data['rooms']:
                        listing_data['rooms'] = text
                    elif 'kvm' in text and not listing_data['size']:
                        listing_data['size'] = text
                    elif 'Ledigt' in text and not listing_data['available']:
                        listing_data['available'] = text

                # Track current addresses
                if listing_data['address'] and listing_data['url']:
                    current_addresses.add(listing_data['address'])

                # Create listing if we have all required fields
                if all(v for k, v in listing_data.items() if k != 'price'):  # Price can be N/A
                    listing = self.create_listing(**listing_data)
                    
                    # Check if listing already exists
                    existing = next((l for l in existing_listings if l['address'] == listing['address']), None)
                    if existing:
                        if not existing.get('active', True):
                            continue
                        
                        # Preserve message_id and channel_id
                        for key in ['message_id', 'channel_id']:
                            if key in existing:
                                listing[key] = existing[key]
                                
                        filtered_listings.append(listing)
                    else:
                        filtered_listings.append(listing)
                        newly_found.append(listing)

            # Handle inactive listings
            removed_listings = []
            for listing in existing_listings:
                if listing['address'] not in current_addresses and listing.get('active', True):
                    listing['active'] = False
                    listing['removed_at'] = datetime.now().strftime('%Y-%m-%d')
                    listing['last_updated'] = datetime.now().isoformat()
                    removed_listings.append(listing)
                    filtered_listings.append(listing)

            return filtered_listings, newly_found, removed_listings, reactivated

        except requests.exceptions.RequestException as e:
            print(f"Error scraping SUBO: {e}")
            return [], [], [], []
