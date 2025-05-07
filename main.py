import requests
from bs4 import BeautifulSoup
import os
import json
import discord
from discord import Embed
from discord import Embed
import asyncio
import argparse
import argparse
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from utils import format_notification_title  # Update import to use relative path
from datetime import datetime
from scrapers.subo import SuboScraper

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"

# Initialize scrapers
SCRAPERS = [
    SuboScraper(),
    # Add more scrapers here as they're implemented
]

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--remove', type=str, help='Address of listing to simulate removal')
    parser.add_argument('--recheck', action='store_true', help='Recheck inactive listings and reactivate if available')
    parser.add_argument('--checkimages', action='store_true', help='Check all messages for missing images')
    parser.add_argument('--clear', action='store_true', help='Delete all existing Discord messages')
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

    async def update_reactivated_listing(self, listing):
        if 'message_id' not in listing:
            return
            
        await self.ensure_connected()
        
        try:
            message = await self.channel.fetch_message(listing['message_id'])
            
            # Create entirely new embed instead of modifying existing one
            embed = Embed(
                title=format_notification_title(listing['url']),
                url=listing['url'],
                color=discord.Color.green()
            )
            
            # Add fields
            embed.add_field(name="Adress", value=f"```{listing['address']}```", inline=False)
            embed.add_field(name="Rum", value=f"```{listing['rooms']}```", inline=True)
            embed.add_field(name="Storlek", value=f"```{listing['size']}```", inline=True)
            embed.add_field(name="Pris", value=f"```{listing['price']}```", inline=True)
            embed.add_field(name="Ledigt", value=f"```{listing['available']}```", inline=False)

            # Set image
            if listing.get('image_url'):
                embed.set_image(url=listing.get('image_url'))
                print(f"Setting image for reactivated listing: {listing['image_url']}")
            
            await message.edit(embed=embed)
            print(f"Successfully updated reactivated listing with image: {listing['address']}")
        except Exception as e:
            print(f"Error updating reactivated listing: {e}")

    async def check_message_images(self, listing):
        if 'message_id' not in listing:
            return
            
        await self.ensure_connected()
        
        try:
            message = await self.channel.fetch_message(listing['message_id'])
            embed = message.embeds[0]
            
            if not embed.image or not embed.image.url:
                print(f"⚠️ Missing image for: {listing['address']}")
                print(f"Expected image URL: {listing.get('image_url', 'No URL stored')}")
                return False
            return True
        except Exception as e:
            print(f"Error checking images for {listing['address']}: {e}")
            return False

    async def clear_messages(self, listings):
        await self.ensure_connected()
        deleted_count = 0
        
        for listing in listings:
            if 'message_id' in listing:
                try:
                    message = await self.channel.fetch_message(listing['message_id'])
                    await message.delete()
                    del listing['message_id']  # Remove message_id from the listing
                    if 'channel_id' in listing:
                        del listing['channel_id']  # Also remove channel_id reference
                    deleted_count += 1
                    print(f"Deleted message for: {listing['address']}")
                except Exception as e:
                    print(f"Failed to delete message for {listing['address']}: {e}")
        
        # Write updated listings back to JSON without message IDs
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(listings, f, indent=2, ensure_ascii=False)
            
        return deleted_count

    async def close(self):
        if self.client:
            await self.client.close()

async def handle_discord_operations(new_listings=None, removed_listings=None, reactivated_listings=None):
    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
    
    try:
        await notifier.ensure_connected()
        
        if reactivated_listings:
            for listing in reactivated_listings:
                await notifier.update_reactivated_listing(listing)
                
        if removed_listings:
            for listing in removed_listings:
                await notifier.update_removed_listing(listing)
        
        if new_listings:
            for listing in new_listings:
                await notifier.send_notification(listing)
    finally:
        await notifier.close()

async def check_all_images(listings, notifier):
    results = []
    for listing in listings:
        has_image = await notifier.check_message_images(listing)
        results.append((listing['address'], has_image))
    return results

def scrape_all_sites(existing_listings):
    all_listings = []
    all_new = []
    all_removed = []
    all_reactivated = []

    for scraper in SCRAPERS:
        listings, new, removed, reactivated = scraper.scrape(existing_listings)
        all_listings.extend(listings)
        all_new.extend(new)
        all_removed.extend(removed)
        all_reactivated.extend(reactivated)
        
    return all_listings, all_new, all_removed, all_reactivated

if __name__ == "__main__":
    args = parse_args()
    
    if args.checkimages:
        if os.path.exists(OUTPUT_JSON_FILE):
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                try:
                    listings = json.load(f)
                    print(f"Checking images for {len(listings)} listings...")
                    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
                    
                    async def run_image_check():
                        await notifier.ensure_connected()
                        results = await check_all_images(listings, notifier)
                        await notifier.close()
                        return results

                    results = asyncio.run(run_image_check())
                    missing_images = [addr for addr, has_image in results if not has_image]
                    
                    if missing_images:
                        print("\nListings with missing images:")
                        for addr in missing_images:
                            print(f"- {addr}")
                    else:
                        print("\nAll listings have images! 🎉")
                        
                except json.JSONDecodeError:
                    print("Error loading listings.json")
        exit(0)

    if args.clear:
        if os.path.exists(OUTPUT_JSON_FILE):
            try:
                # First load and store current listings
                with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                    listings = json.load(f)
                
                if listings:
                    print(f"Clearing {len(listings)} messages...")
                    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)
                    
                    async def run_clear():
                        await notifier.ensure_connected()
                        deleted = await notifier.clear_messages(listings)
                        await notifier.close()
                        return deleted

                    deleted_count = asyncio.run(run_clear())
                    print(f"Successfully deleted {deleted_count} messages")
                
                # After deleting messages, empty the JSON file
                with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                    print("Successfully emptied listings.json")
                    
            except Exception as e:
                print(f"Error during clear operation: {e}")
        exit(0)

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
        # Normal scraping mode - now uses all scrapers
        all_listings, newly_found_listings, removed_listings, reactivated = scrape_all_sites(
            existing_listings if 'existing_listings' in locals() else []
        )

    # Always write the full listings to JSON
    if all_listings:
        with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(all_listings, f, indent=2, ensure_ascii=False)
        
        if removed_listings or newly_found_listings or reactivated:
            asyncio.run(handle_discord_operations(
                new_listings=newly_found_listings,
                removed_listings=removed_listings,
                reactivated_listings=reactivated
            ))