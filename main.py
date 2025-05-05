import requests
from bs4 import BeautifulSoup
import os
import json
import discord
from discord import Embed
import asyncio
import argparse
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from utils import format_notification_title  # Update import to use relative path
from datetime import datetime

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--remove', type=str, help='Address of listing to simulate removal')
    return parser.parse_args()

class DiscordNotifier:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self._ready = asyncio.Event()
        self.channel = None
        
        @self.client.event
        async def on_ready():
            self.channel = self.client.get_channel(self.channel_id)
            self._ready.set()

    async def connect(self):
        try:
            await self.client.start(self.token)
        except Exception as e:
            print(f"Failed to connect to Discord: {e}")
            raise

    async def ensure_connected(self):
        if not self.client.is_ready():
            connect_task = asyncio.create_task(self.connect())
            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30)
            except asyncio.TimeoutError:
                connect_task.cancel()
                raise TimeoutError("Failed to connect to Discord within 30 seconds")
            
        if not self.channel:
            self.channel = self.client.get_channel(self.channel_id)
            if not self.channel:
                raise ValueError(f"Could not find channel {self.channel_id}")

    async def send_notification(self, listing):
        await self.ensure_connected()

        # Title formatting with proper emoji spacing for strikethrough
        title = format_notification_title(listing['url'])
        if not listing.get('active', True):
            # Split emoji and text to prevent emoji from being struck through
            parts = title.split(' ', 1)
            title = f"{parts[0]} ~~{parts[1]}~~"

        embed = Embed(
            title=title,
            url=listing['url'] if listing.get('active', True) else None,
            color=discord.Color.green() if listing.get('active', True) else discord.Color.red()
        )

        # Add fields with conditional strikethrough
        value_format = "```{}```" if listing.get('active', True) else "```{}```"
        name_format = "{}" if listing.get('active', True) else "~~{}~~"

        # If inactive, show removal date instead of availability
        available_text = listing['available']
        if not listing.get('active', True):
            available_text = f"Borttagen {datetime.now().strftime('%Y-%m-%d')}"

        embed.add_field(name=name_format.format("Adress"), value=value_format.format(listing['address']), inline=False)
        embed.add_field(name=name_format.format("Rum"), value=value_format.format(listing['rooms']), inline=True)
        embed.add_field(name=name_format.format("Storlek"), value=value_format.format(listing['size']), inline=True)
        embed.add_field(name=name_format.format("Pris"), value=value_format.format(listing['price']), inline=True)
        embed.add_field(name=name_format.format("Ledigt"), value=value_format.format(available_text), inline=False)

        # Handle image
        if listing.get('image_url'):
            embed.set_image(url=listing.get('image_url'))

        try:
            msg = await self.channel.send(embed=embed)
            # Save message ID and add channel ID for reference
            listing['message_id'] = msg.id
            listing['channel_id'] = self.channel_id
            # Write updated listings to JSON immediately after sending message
            with open(OUTPUT_JSON_FILE, "r+", encoding="utf-8") as f:
                listings = json.load(f)
                # Update or add the listing with message info
                found = False
                for idx, l in enumerate(listings):
                    if l['address'] == listing['address']:
                        listings[idx]['message_id'] = msg.id
                        listings[idx]['channel_id'] = self.channel_id
                        found = True
                        break
                if not found:
                    listings.append(listing)
                # Write back to file
                f.seek(0)
                json.dump(listings, f, indent=2, ensure_ascii=False)
                f.truncate()
            return msg
        except Exception as e:
            print(f"Error sending message: {e}")

    async def update_removed_listing(self, listing):
        if 'message_id' not in listing:
            return
            
        await self.ensure_connected()
        
        try:
            message = await self.channel.fetch_message(listing['message_id'])
            embed = message.embeds[0]
            
            # Split emoji and text to prevent emoji from being struck through
            title = embed.title
            parts = title.split(' ', 1)
            embed.title = f"{parts[0]} ~~{parts[1]}~~"
            
            embed.url = None
            embed.color = discord.Color.red()

            # Clear existing fields
            embed.clear_fields()
            
            # Re-add fields with strikethrough names and current date
            current_date = datetime.now().strftime('%Y-%m-%d')
            embed.add_field(name="~~Adress~~", value=f"```{listing['address']}```", inline=False)
            embed.add_field(name="~~Rum~~", value=f"```{listing['rooms']}```", inline=True)
            embed.add_field(name="~~Storlek~~", value=f"```{listing['size']}```", inline=True)
            embed.add_field(name="~~Pris~~", value=f"```{listing['price']}```", inline=True)
            embed.add_field(name="~~Ledigt~~", value=f"```Borttagen {current_date}```", inline=False)
            
            await message.edit(embed=embed)
        except Exception as e:
            print(f"Error updating removed listing: {e}")

    async def close(self):
        if self.client:
            await self.client.close()

async def handle_discord_operations(new_listings=None, removed_listings=None):
    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
    
    try:
        await notifier.ensure_connected()
        
        if removed_listings:
            for listing in removed_listings:
                await notifier.update_removed_listing(listing)
        
        if new_listings:
            for listing in new_listings:
                await notifier.send_notification(listing)
    finally:
        await notifier.close()

def scrape_website_one(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        new_listings = []
        elementor_divs = soup.find_all('div', class_='elementor')
        listing_containers = [item for item in elementor_divs if item.get('data-elementor-type') == 'jet-listing-items']

        # Load all existing listings - we'll keep these and just update their status
        existing_listings = []
        if os.path.exists(OUTPUT_JSON_FILE):
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                try:
                    existing_listings = json.load(f)
                except json.JSONDecodeError:
                    pass

        # Create a set of current addresses before starting scraping
        current_addresses = set()

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
            image_url = None

            # First try to find image URL from parent container's style tag
            parent_item = item.find_parent('div', class_='jet-listing-grid__item')
            if parent_item:
                style_tag = parent_item.find('style')
                if style_tag:
                    style_content = style_tag.string
                    if style_content and 'background-image' in style_content:
                        import re
                        match = re.search(r'background-image:\s*url\(["\'](.+?)["\']\)', style_content)
                        if match:
                            image_url = match.group(1)

            # Fallback to existing methods if parent style tag didn't work
            if not image_url:
                style_tag = item.find('style')
                if style_tag:
                    style_content = style_tag.string
                    if style_content and 'background-image' in style_content:
                        match = re.search(r'background-image:\s*url\("([^"]+)"\)', style_content)
                        if match:
                            image_url = match.group(1)
            
            # Fallbacks if style tag method doesn't work
            if not image_url:
                # Try to find the image URL from the background-image style
                image_container = item.find('div', class_='elementor-column-wrap')
                if image_container and 'style' in image_container.attrs:
                    style = image_container.attrs['style']
                    if 'background-image' in style:
                        match = re.search(r'url\("([^"]+)"\)', style)
                        if match:
                            image_url = match.group(1)
            
                # If still not found, try finding a direct img tag
                if not image_url:
                    img_tag = item.find('img')
                    if img_tag and 'src' in img_tag.attrs:
                        image_url = img_tag.attrs['src']

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

            if url and address:  # Track address as soon as we find it
                current_addresses.add(address)

            if url and address and price and rooms and size and available:
                # Check if listing already exists
                existing_listing = next((l for l in existing_listings if l['address'] == address), None)
                
                if existing_listing:
                    # Skip if manually marked as inactive
                    if existing_listing.get('active') is False:
                        continue
                    
                    # Update existing listing while preserving message_id
                    message_id = existing_listing.get('message_id')
                    existing_listing.update({
                        'url': url,
                        'price': price,
                        'size': size,
                        'rooms': rooms,
                        'available': available,
                        'image_url': image_url,
                        'active': True
                    })
                    if message_id:
                        existing_listing['message_id'] = message_id
                else:
                    # Create new listing
                    new_listing = {
                        'address': address,
                        'url': url,
                        'price': price,
                        'size': size,
                        'rooms': rooms,
                        'available': available,
                        'image_url': image_url,
                        'active': True
                    }
                    existing_listings.append(new_listing)
                    newly_found.append(new_listing)
            else:
                incomplete_count += 1

                if url and address and not price and rooms and size and available:
                    existing_listing = next((l for l in existing_listings if l['address'] == address), None)
                    
                    # Skip if manually deactivated
                    if existing_listing and existing_listing.get('active') is False:
                        continue

                    listing_na = {
                        'address': address,
                        'url': url,
                        'price': 'N/A',
                        'size': size,
                        'rooms': rooms,
                        'available': available,
                        'image_url': image_url,
                        'active': True
                    }

                    if existing_listing:
                        # Update existing listing while preserving message_id
                        message_id = existing_listing.get('message_id')
                        existing_listing.update(listing_na)
                        if message_id:
                            existing_listing['message_id'] = message_id
                    elif listing_na not in existing_listings:
                        existing_listings.append(listing_na)
                        newly_found.append(listing_na)

        # After scraping, mark listings as inactive only if not found
        for listing in existing_listings:
            # Only change status if:
            # 1. Address not found in current scrape
            # 2. Not already manually deactivated
            if listing['address'] not in current_addresses and listing.get('active') is not False:
                listing['active'] = False
                listing['removed_at'] = datetime.now().strftime("%Y-%m-%d")

        # Find listings that need to be marked as removed
        removed_listings = [l for l in existing_listings 
                          if l.get('message_id') and not l['active']]
        
        print(f"Found {len(newly_found)} new listings, {len(removed_listings)} removed/inactive")

        return existing_listings, newly_found, removed_listings

    except requests.exceptions.RequestException as e:
        return [], [], []
    return [], [], []

if __name__ == "__main__":
    args = parse_args()
    website_one_url = "https://www.subo.se/lediga-lagenheter/"
    
    if args.debug:
        # Debug mode - use existing listings as the base
        all_listings = []
        # Copy listings while preserving message_id
        for listing in existing_listings:
            new_listing = listing.copy()
            if 'message_id' in listing:
                new_listing['message_id'] = listing['message_id']
            all_listings.append(new_listing)

        newly_found_listings = []
        removed_listings = []
        
        if args.remove:
            # Find and mark the listing as inactive
            for listing in all_listings:
                if listing['address'] == args.remove:
                    listing['active'] = False
                    listing['removed_at'] = datetime.now().strftime("%Y-%m-%d")
                    removed_listings.append(listing)
                    break  # Exit once we find the matching listing
    else:
        # Normal scraping mode
        all_listings, newly_found_listings, removed_listings = scrape_website_one(website_one_url)

    # Always write the full listings to JSON
    if all_listings:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_listings, f, indent=2, ensure_ascii=False)
        
        if removed_listings or newly_found_listings:
            asyncio.run(handle_discord_operations(
                new_listings=newly_found_listings,
                removed_listings=removed_listings
            ))