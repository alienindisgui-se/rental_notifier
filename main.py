import requests
from bs4 import BeautifulSoup
import os
import json
import discord
from discord import Embed
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from utils import format_notification_title  # Update import to use relative path

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"

async def send_discord_notification(listing):
    """Sends an embed message to the specified Discord channel."""
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    # Validate and clean image URL
    image_url = listing.get('image_url', '').strip()
    if image_url:
        # Add https if missing
        if not image_url.startswith(('http://', 'https://')):
            image_url = 'https://' + image_url
        # Ensure proper URL encoding
        image_url = image_url.replace(' ', '%20')
        print(f"Processing image URL: {image_url}")

    try:
        @client.event
        async def on_ready():
            try:
                channel = client.get_channel(DISCORD_CHANNEL_ID)
                if channel:
                    embed = Embed(
                        title=format_notification_title(listing['url']),
                        url=listing['url'],
                        color=0x00AE86,
                        description=f"```{listing['address']}```"  # Move address to description for better spacing
                    )
                    
                    # Group Rum/Storlek together without any spacing
                    embed.add_field(name="Rum", value=f"```{listing['rooms']}```", inline=True)
                    embed.add_field(name="Storlek", value=f"```{listing['size']}```", inline=True)
                    
                    # Group Pris/Ledigt together without any spacing
                    embed.add_field(name="Pris", value=f"```{listing['price']}```", inline=True)
                    embed.add_field(name="Ledigt", value=f"```{listing['available']}```", inline=True)

                    # Handle image separately with retries
                    if image_url:
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                embed.set_image(url=image_url)
                                print(f"Successfully set image URL on attempt {retry_count + 1}")
                                break
                            except Exception as e:
                                retry_count += 1
                                print(f"Failed to set image URL (attempt {retry_count}): {e}")
                                if retry_count == max_retries:
                                    print(f"Failed to set image after {max_retries} attempts for {listing['address']}")
                                await asyncio.sleep(1)  # Wait before retry
                    
                    # Send the message with final status
                    try:
                        msg = await channel.send(embed=embed)
                        print(f"Notification sent for {listing['address']}")
                        if not msg.embeds[0].image:
                            print(f"Warning: Image failed to attach for {listing['address']}")
                    except Exception as e:
                        print(f"Failed to send message: {e}")
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

            if url and address and price and rooms and size and available:
                listing = {
                    'address': address,
                    'url': url,
                    'price': price,
                    'size': size,
                    'rooms': rooms,
                    'available': available,
                    'image_url': image_url  # Add image URL to the listing
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
                if not image_url:
                    missing_info.append("image_url")
                print(", ".join(missing_info))
                print(f"Saved incomplete listing HTML to: {filename}")

                # Add image URL debugging information
                if not image_url:
                    print("Image URL debugging:")
                    style_tag = item.find('style')
                    if style_tag:
                        print(f"Style tag content: {style_tag.string}")
                    
                    image_container = item.find('div', class_='elementor-column-wrap')
                    if image_container and 'style' in image_container.attrs:
                        print(f"Image container style: {image_container.attrs['style']}")
                    
                    img_tag = item.find('img')
                    if img_tag:
                        print(f"Direct img tag: {img_tag}")

                    # Save detailed image debugging to a separate file
                    debug_image_file = os.path.join(DEBUG_OUTPUT_DIR, f"image_debug_{incomplete_count}.txt")
                    with open(debug_image_file, "w", encoding="utf-8") as f:
                        f.write("Style tag content:\n")
                        f.write(str(style_tag.string if style_tag else "Not found") + "\n\n")
                        f.write("Image container style:\n")
                        f.write(str(image_container.attrs['style'] if image_container and 'style' in image_container.attrs else "Not found") + "\n\n")
                        f.write("Direct img tag:\n")
                        f.write(str(img_tag) if img_tag else "Not found")

                if url and address and not price and rooms and size and available:
                    listing_na = {
                        'address': address,
                        'url': url,
                        'price': 'N/A',
                        'size': size,
                        'rooms': rooms,
                        'available': available,
                        'image_url': image_url  # Add image URL here too
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
        # Write all listings to the JSON file with compact formatting
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_listings, f, indent=2, ensure_ascii=False, separators=(',', ': '))
        print(f"Saved {len(all_listings)} listings to {OUTPUT_JSON_FILE}")

        if newly_found_listings:
            for listing in newly_found_listings:
                asyncio.run(send_discord_notification(listing))
        else:
            print("No new listings found.")
    else:
        print("No listings found.")