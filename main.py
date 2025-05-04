import requests
from bs4 import BeautifulSoup
import os
import json

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"  # Define the output JSON filename

def scrape_website_one(url):
    print(f"Scraping URL: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        print("Successfully fetched and parsed the page.")

        new_listings = []
        elementor_divs = soup.find_all('div', class_='elementor')
        listing_containers = [item for item in elementor_divs if item.get('data-elementor-type') == 'jet-listing-items']
        print(f"Found {len(listing_containers)} potential listing containers.")

        # Create the debug output directory if it doesn't exist
        if not os.path.exists(DEBUG_OUTPUT_DIR):
            os.makedirs(DEBUG_OUTPUT_DIR)

        incomplete_count = 0
        for item in listing_containers:
            url_element = item.find('div', class_='make-column-clickable-elementor')
            url = url_element.get('data-column-clickable') if url_element else None
            h2_elements = item.find_all('h2', class_='elementor-heading-title')

            address = None
            price = None
            rooms = None
            size = None
            available = None

            if len(h2_elements) >= 4:  # Adjusted minimum h2 count
                for h2 in h2_elements:
                    text = h2.text.strip()
                    if ',' in text and not address:  # Removed the 'not text.startswith('Möblerat')' condition
                        address = text
                    elif ':-/månad' in text and not price:
                        price = text
                    elif 'rum' in text and any(char.isdigit() for char in text) and not rooms:
                        rooms = text
                    elif 'kvm' in text and not size:
                        size = text

            # Logic to find availability
            available_element = item.find('h2', class_='elementor-heading-title', string=lambda text: text and 'Ledigt' in text)
            if available_element:
                available = available_element.text.strip()
            else:
                ledig_button = item.find('div', class_='elementor-widget-button')
                if ledig_button:
                    ledig_span = ledig_button.find('span', class_='elementor-button-text')
                    if ledig_span and ledig_span.text.strip() == 'Ledig':
                        next_heading = ledig_button.find_parent('div', class_='elementor-element').find_next_sibling('div').find('h2', class_='elementor-heading-title') if ledig_button.find_parent('div', class_='elementor-element').find_next_sibling('div') else None
                        if next_heading and 'från' in next_heading.text:
                            available = next_heading.text.strip()
                        else:
                            available = 'Ledig'
                        if not address:
                            prev_heading = ledig_button.find_parent('div', class_='elementor-element').find_previous_sibling('div').find('h2', class_='elementor-heading-title') if ledig_button.find_parent('div', class_='elementor-element').find_previous_sibling('div') else None
                            if prev_heading and ',' in prev_heading.text:
                                address = prev_heading.text.strip()

            if url and address and price and rooms and size and available:
                new_listings.append({
                    'address': address,
                    'url': url,
                    'price': price,
                    'size': size,
                    'rooms': rooms,
                    'available': available
                })
            else:
                incomplete_count += 1
                filename = os.path.join(DEBUG_OUTPUT_DIR, f"incomplete_listing_{incomplete_count}.html")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(item.prettify())
                print(f"Incomplete data in listing {incomplete_count}. Missing:", end=" ")
                missing_info = []
                if not url:
                    missing_info.append("url")
                if not address:
                    missing_info.append("address")
                if not price:
                    missing_info.append("price")
                if not rooms:
                    missing_info.append("rooms")
                if not size:
                    missing_info.append("size")
                if not available:
                    missing_info.append("available")
                print(", ".join(missing_info))
                print(f"Saved incomplete listing HTML to: {filename}")

                # If only price is missing, add to listings with price as "N/A"
                if url and address and not price and rooms and size and available:
                    new_listings.append({
                        'address': address,
                        'url': url,
                        'price': 'N/A',
                        'size': size,
                        'rooms': rooms,
                        'available': available
                    })
                    print(f"Added listing {incomplete_count} with price as 'N/A'")

        print(f"Found {len(new_listings)} new listings.")
        return new_listings
    except requests.exceptions.RequestException as e:
        print(f"Error scraping {url}: {e}")
        return []

if __name__ == "__main__":
    website_one_url = "https://www.subo.se/lediga-lagenheter/"
    listings = scrape_website_one(website_one_url)

    if listings:
        # Write the listings to a JSON file
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(listings, f, indent=4, ensure_ascii=False)  #  ensure_ascii=False for non-ASCII characters
        print(f"Saved {len(listings)} listings to {OUTPUT_JSON_FILE}")
    else:
        print("No listings found.")