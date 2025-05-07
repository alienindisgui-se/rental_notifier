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
from scrapers.dios import DiosScraper  # Updated import path

DEBUG_OUTPUT_DIR = "debug_output"
OUTPUT_JSON_FILE = "listings.json"

# Initialize scrapers
ALL_SCRAPERS = {
    'subo': SuboScraper(),
    'dios': DiosScraper()
}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--remove', type=str, help='Address of listing to simulate removal')
    parser.add_argument('--recheck', action='store_true', help='Recheck inactive listings and reactivate if available')
    parser.add_argument('--clear', action='store_true', help='Delete all existing Discord messages')
    parser.add_argument('--subo', action='store_true', help='Run only SUBO scraper')
    parser.add_argument('--dios', action='store_true', help='Run only Dios scraper')
    return parser.parse_args()

def get_active_scrapers(args):
    if args.subo:
        print("Running SUBO scraper only")
        return [ALL_SCRAPERS['subo']]
    elif args.dios:
        print("Running Dios scraper only")
        return [ALL_SCRAPERS['dios']]
    print("Running all scrapers")
    return ALL_SCRAPERS.values()

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
        embed.add_field(name=name_format.format("Hyra"), value=value_format.format(listing['price']), inline=True)
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
                # Update or add the listing with message info using URL as unique identifier
                found = False
                for idx, l in enumerate(listings):
                    if l['url'] == listing['url']:  # Changed from address to url
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
            embed.add_field(name="~~Hyra~~", value=f"```{listing['price']}```", inline=True)
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
            embed.add_field(name="Hyra", value=f"```{listing['price']}```", inline=True)
            embed.add_field(name="Ledigt", value=f"```{listing['available']}```", inline=False)

            # Set image
            if listing.get('image_url'):
                embed.set_image(url=listing.get('image_url'))
                print(f"Setting image for reactivated listing: {listing['image_url']}")
            
            await message.edit(embed=embed)
            print(f"Successfully updated reactivated listing with image: {listing['address']}")
        except Exception as e:
            print(f"Error updating reactivated listing: {e}")

    async def clear_messages(self, listings):
        await self.ensure_connected()
        deleted_count = 0
        
        # Collect all message IDs first
        message_ids = [(listing.get('message_id'), listing) for listing in listings if listing.get('message_id')]
        print(f"Found {len(message_ids)} message IDs to delete")
        
        for msg_id, listing in message_ids:
            try:
                message = await self.channel.fetch_message(msg_id)
                await message.delete()
                deleted_count += 1
                print(f"Deleted message ID for: {listing['address']} | {listing['size']} | {listing['rooms']}")
                
            except Exception as e:
                print(f"Failed to delete message for {listing['address']}: {e}")
        
        # Clear message IDs from listings
        for listing in listings:
            if 'message_id' in listing:
                del listing['message_id']
            if 'channel_id' in listing:
                del listing['channel_id']
        
        # Write updated listings back to JSON
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
        print(f"\nProcessing Discord notifications:")
        
        if new_listings:
            print(f"Sending {len(new_listings)} new listings...")
            for listing in new_listings:
                print(f"Sending notification for: {listing['address']} | {listing['size']} | {listing['rooms']}")
                message = await notifier.send_notification(listing)
                if message:
                    listing['message_id'] = message.id
                    listing['channel_id'] = message.channel.id
                else:
                    print(f"Failed to send notification for: {listing['address']}")
                await asyncio.sleep(1)  # 1 second delay between messages
        
        if reactivated_listings:
            print(f"Updating {len(reactivated_listings)} reactivated listings...")
            for listing in reactivated_listings:
                await notifier.update_reactivated_listing(listing)
                await asyncio.sleep(1)  # 1 second delay between updates
                
        if removed_listings:
            print(f"Updating {len(removed_listings)} removed listings...")
            for listing in removed_listings:
                await notifier.update_removed_listing(listing)
                await asyncio.sleep(1)  # 1 second delay between updates

    except Exception as e:
        print(f"Error in Discord operations: {e}")
    finally:
        await notifier.close()

def scrape_all_sites(existing_listings, scrapers):
    print(f"\nStarting scrape with {len(existing_listings)} existing listings")
    all_listings = []
    all_new = []
    all_removed = []
    all_reactivated = []

    for scraper in scrapers:
        print(f"\nRunning {scraper.__class__.__name__}")
        listings, new, removed, reactivated = scraper.scrape(existing_listings)
        all_listings.extend(listings)
        all_new.extend(new)
        all_removed.extend(removed)
        all_reactivated.extend(reactivated)
        
    print(f"\nScraping complete:")
    print(f"Total listings: {len(all_listings)}")
    print(f"New listings: {len(all_new)}")
    print(f"Removed: {len(all_removed)}")
    print(f"Reactivated: {len(all_reactivated)}")
    
    return all_listings, all_new, all_removed, all_reactivated

if __name__ == "__main__":
    args = parse_args()
    
    # Load existing listings at the start
    existing_listings = []
    if os.path.exists(OUTPUT_JSON_FILE):
        try:
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                existing_listings = json.load(f)
        except json.JSONDecodeError:
            print("Error loading listings.json")

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
                    break
    else:
        # Normal scraping mode - now uses selected scrapers
        active_scrapers = get_active_scrapers(args)
        all_listings, newly_found_listings, removed_listings, reactivated = scrape_all_sites(
            existing_listings,
            active_scrapers
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