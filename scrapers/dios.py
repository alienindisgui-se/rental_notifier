import re
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import os
from .base import RentalScraper
import json

class DiosScraper(RentalScraper):
    def __init__(self):
        self.url = "https://www.dios.se/api/bostad"
        self.base_url = "https://www.dios.se"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }

    def get_listing_details(self, url):
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            details = {}

            # Get size
            size_number = soup.find('span', class_='object-factshighlightnumber')
            size_unit = size_number.find_next_sibling('span', class_='object-factshighlightunit') if size_number else None
            if size_number and size_unit:
                details['size'] = f"{size_number.text.strip()} {size_unit.text.strip()}"

            # Get rooms
            rooms_number = soup.find_all('span', class_='object-factshighlightnumber')[1] if len(soup.find_all('span', class_='object-factshighlightnumber')) > 1 else None
            rooms_unit = rooms_number.find_next_sibling('span', class_='object-factshighlightunit') if rooms_number else None
            if rooms_number and rooms_unit:
                details['rooms'] = f"{rooms_number.text.strip()} {rooms_unit.text.strip()}"

            # Get available date
            available_title = soup.find('dt', class_='object-factshighlightdetailtitle', string='Tillträde')
            if available_title:
                available_value = available_title.find_next_sibling('dd', class_='object-factshighlightdetailvalue')
                if available_value:
                    details['available'] = available_value.text.strip()

            return details
        except Exception as e:
            print(f"Error getting details from {url}: {e}")
            return None

    def scrape(self, existing_listings):
        try:
            print("\n=== Starting Dios Scraper ===")
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            
            listings_data = response.json()
            
            sundsvall_listings = [l for l in listings_data if l['city'].upper() == 'SUNDSVALL']
            
            current_urls = set()
            newly_found = []
            filtered_listings = []
            reactivated = []
            
            for item in sundsvall_listings:
                try:
                    full_url = f"{self.base_url}{item['url']}"
                    current_urls.add(full_url)
                    
                    # Get additional details from listing page
                    details = self.get_listing_details(full_url)
                    if not details:
                        continue

                    address_match = re.search(r'(\d+)\s*kvm\s+på\s+([^,]+)', item['name'])
                    if not address_match:
                        continue
                        
                    address = address_match.group(2).strip()
                    
                    listing = self.create_listing(
                        address=address,
                        url=full_url,
                        size=details.get('size', f"{item['areaTotal']} KVM"),
                        rooms=details.get('rooms', 'N/A'),
                        price=f"{item['rent']}:-/månad",
                        available=details.get('available', 'Kontakta uthyrare'),
                        image_url=f"{self.base_url}{item['image']}" if item.get('image') else None
                    )
                    
                    existing = next((l for l in existing_listings if l['url'] == full_url), None)
                    if existing:
                        if not existing.get('active', True):
                            reactivated.append(listing)
                        for key in ['message_id', 'channel_id']:
                            if key in existing:
                                listing[key] = existing[key]
                        filtered_listings.append(listing)
                    else:
                        filtered_listings.append(listing)
                        newly_found.append(listing)
                        
                except Exception as e:
                    print(f"Error processing listing: {str(e)}")
                    continue

            removed_listings = []
            for listing in existing_listings:
                if listing['source'] == 'DiosScraper' and listing['url'] not in current_urls and listing.get('active', True):
                    listing['active'] = False
                    listing['removed_at'] = datetime.now().strftime('%Y-%m-%d')
                    removed_listings.append(listing)
                    filtered_listings.append(listing)

            return filtered_listings, newly_found, removed_listings, reactivated
            
        except Exception as e:
            print(f"Error in Dios scraper: {str(e)}")
            return [], [], [], []
