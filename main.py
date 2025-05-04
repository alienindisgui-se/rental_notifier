import requests
from bs4 import BeautifulSoup
import os
import json
import discord
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"

async def send_discord_notification(message):
    """Sends a message to the specified Discord channel."""
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    try:
        @client.event
        async def on_ready():
            try:
                channel = client.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    await channel.send(message)
            finally:
                await client.close()

        await client.start(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        print("Discord bot login failed. Please check your token.")
    except Exception as e:
        print(f"An error occurred while connecting to Discord: {e}")
    finally:
        if not client.is_closed():
            await client.close()

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

        # Load existing listings
        existing_listings = []
        if os.path.exists(OUTPUT_JSON_FILE):
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                try:
                    existing_listings = json.load(f)
                except json.JSONDecodeError:
                    print("Error decoding existing listings JSON. Starting with an empty list.")

        newly_found = []
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

            for h2 in h2_elements:
                text = h2.text.strip()
                if ',' in text and not address:
                    address = text
                elif ':-/månad' in text and not price:
                    price = text
                elif 'rum' in text and any(char.isdigit() for char in text) and not rooms:
                    rooms = text
                elif 'kvm' in text and not size:
                    size = text
                elif not price and any(char.isdigit() for char in text) and ('kr/månad' in text or ':-/mån' in text or 'kr/mån' in text): # More flexible price matching
                    price = text
                # --- Add moreIntegrate Discord bot for new listing notifications price extraction logic here if needed based on incomplete_listing_1.html ---

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
                listing = {
                    'address': address,
                    'url': url,
                    'price': price,
                    'size': size,
                    'rooms': rooms,
                    'available': available
                }
                if listing not in existing_listings:
                    new_listings.append(listing)
                    newly_found.append(listing)
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

                if url and address and not price and rooms and size and available:
                    listing_na = {
                        'address': address,
                        'url': url,
                        'price': 'N/A',
                        'size': size,
                        'rooms': rooms,
                        'available': available
                    }
                    if listing_na not in existing_listings:
                        new_listings.append(listing_na)
                        newly_found.append(listing_na)
                    print(f"Added incomplete listing {incomplete_count} with price as 'N/A'")

        print(f"Found {len(new_listings)} new listings (including those with N/A price).")
        return new_listings, newly_found

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return [], []
    return [], []

if __name__ == "__main__":
    website_one_url = "https://www.subo.se/lediga-lagenheter/"
    all_listings, newly_found_listings = scrape_website_one(website_one_url)

    if all_listings:
        # Write all listings to the JSON file
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_listings, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(all_listings)} listings to {OUTPUT_JSON_FILE}")

        if newly_found_listings:
            for listing in newly_found_listings:
                message = f"Ny lägenhet hittad!\nAdress: {listing['address']}\nPris: {listing['price']}\nStorlek: {listing['size']}\nRum: {listing['rooms']}\nLedigt: {listing['available']}\nLänk: {listing['url']}"
                asyncio.run(send_discord_notification(message))
        else:
            print("No new listings found.")
    else:
        print("No listings found.")