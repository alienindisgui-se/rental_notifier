import requests
from bs4 import BeautifulSoup
import os
import json
import discord
from discord import Embed # Removed duplicate import
import asyncio
import argparse # Removed duplicate import
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
from utils import format_notification_title
from datetime import datetime
# Assuming scraper classes are in scrapers/subo.py and scrapers/dios.py
from scrapers.subo import SuboScraper
from scrapers.dios import DiosScraper

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
        # Enable the message_content intent if needed for fetching messages
        # intents.message_content = True
        self.client = discord.Client(intents=intents)
        self._ready = asyncio.Event()
        self.channel = None

        @self.client.event
        async def on_ready():
            self.channel = self.client.get_channel(self.channel_id)
            self._ready.set()

    async def connect(self):
        try:
            # Use run instead of start to keep the bot running for async operations
            await self.client.start(self.token)
        except Exception as e:
            print(f"Failed to connect to Discord: {e}")
            raise

    async def ensure_connected(self):
        # Check if the client is already connected and ready
        if not self.client.is_ready():
             # If not ready, start the client in a separate task
            connect_task = asyncio.create_task(self.client.start(self.token))
            try:
                # Wait for the on_ready event to be set
                await asyncio.wait_for(self._ready.wait(), timeout=30)
            except asyncio.TimeoutError:
                # If timeout occurs, cancel the connection task and raise an error
                connect_task.cancel()
                raise TimeoutError("Failed to connect to Discord within 30 seconds")

        # Ensure the channel object is available
        if not self.channel:
            self.channel = self.client.get_channel(self.channel_id)
            if not self.channel:
                raise ValueError(f"Could not find channel with ID {self.channel_id}")


    async def send_notification(self, listing):
        # Ensure the bot is connected before sending
        await self.ensure_connected()

        # Title formatting with proper emoji spacing for strikethrough
        title = format_notification_title(listing['url'])
        # Apply strikethrough only if the listing is marked as inactive
        if not listing.get('active', True):
            # Split emoji and text to prevent emoji from being struck through
            parts = title.split(' ', 1)
            # Reconstruct title with strikethrough on the text part
            title = f"{parts[0]} ~~{parts[1]}~~"

        # Create the embed message
        embed = Embed(
            title=title,
            # Set URL only if the listing is active
            url=listing['url'] if listing.get('active', True) else None,
            # Set color based on active status
            color=discord.Color.green() if listing.get('active', True) else discord.Color.red()
        )

        # Define formatting for field values and names (with conditional strikethrough)
        value_format = "```{}```" # Use code block for values
        name_format = "{}" if listing.get('active', True) else "~~{}~~" # Apply strikethrough to names if inactive

        # Determine the text for the 'Ledigt' field
        available_text = listing.get('available', 'N/A') # Use .get for safety
        # If inactive, show removal date instead of availability
        if not listing.get('active', True):
            # Use the 'removed_at' field if available, otherwise use current date
            removal_date = listing.get('removed_at', datetime.now().strftime('%Y-%m-%d'))
            available_text = f"Borttagen {removal_date}"

        # Add fields to the embed
        embed.add_field(name=name_format.format("Adress"), value=value_format.format(listing.get('address', 'N/A')), inline=False)
        embed.add_field(name=name_format.format("Rum"), value=value_format.format(listing.get('rooms', 'N/A')), inline=True)
        embed.add_field(name=name_format.format("Storlek"), value=value_format.format(listing.get('size', 'N/A')), inline=True)
        embed.add_field(name=name_format.format("Hyra"), value=value_format.format(listing.get('price', 'N/A')), inline=True)
        embed.add_field(name=name_format.format("Ledigt"), value=value_format.format(available_text), inline=False)

        # Handle image if URL is provided
        if listing.get('image_url'):
            embed.set_image(url=listing.get('image_url'))

        try:
            # Send the embed message to the channel
            msg = await self.channel.send(embed=embed)
            # Store the message ID and channel ID in the listing data
            listing['message_id'] = msg.id
            listing['channel_id'] = self.channel_id
            # Note: The listings list is updated in the main execution block
            # after all notifications are processed for better file handling.
            return msg
        except Exception as e:
            print(f"Error sending message for {listing.get('address', 'Unknown')}: {e}")
            return None # Return None if sending fails

    async def update_removed_listing(self, listing):
        # Ensure the bot is connected and the listing has a message ID
        if 'message_id' not in listing:
            print(f"Skipping update for removed listing with no message_id: {listing.get('address', 'Unknown')}")
            return

        await self.ensure_connected()

        try:
            # Fetch the original message from Discord
            message = await self.channel.fetch_message(listing['message_id'])
            # Get the existing embed
            embed = message.embeds[0]

            # Apply strikethrough to the title text (preserving emoji)
            title = embed.title
            parts = title.split(' ', 1)
            embed.title = f"{parts[0]} ~~{parts[1]}~~"

            # Remove the URL and change color to red
            embed.url = None
            embed.color = discord.Color.red()

            # Clear existing fields before adding updated ones
            embed.clear_fields()

            # Re-add fields with strikethrough names and current date for availability
            current_date = datetime.now().strftime('%Y-%m-%d')
            embed.add_field(name="~~Adress~~", value=f"```{listing.get('address', 'N/A')}```", inline=False)
            embed.add_field(name="~~Rum~~", value=f"```{listing.get('rooms', 'N/A')}```", inline=True)
            embed.add_field(name="~~Storlek~~", value=f"```{listing.get('size', 'N/A')}```", inline=True)
            embed.add_field(name="~~Hyra~~", value=f"```{listing.get('price', 'N/A')}```", inline=True)
            embed.add_field(name="~~Ledigt~~", value=f"```Borttagen {current_date}```", inline=False)

            # Edit the message with the updated embed
            await message.edit(embed=embed)
            print(f"Successfully updated removed listing message for: {listing.get('address', 'Unknown')}")
        except discord.errors.NotFound:
             print(f"Message with ID {listing['message_id']} not found for removed listing: {listing.get('address', 'Unknown')}")
        except Exception as e:
            print(f"Error updating removed listing message for {listing.get('address', 'Unknown')}: {e}")


    async def update_reactivated_listing(self, listing):
        # Ensure the bot is connected and the listing has a message ID
        if 'message_id' not in listing:
            print(f"Skipping update for reactivated listing with no message_id: {listing.get('address', 'Unknown')}")
            return

        await self.ensure_connected()

        try:
            # Fetch the original message
            message = await self.channel.fetch_message(listing['message_id'])

            # Create a new embed for the reactivated listing
            embed = Embed(
                title=format_notification_title(listing['url']), # Use original title format
                url=listing['url'], # Restore the URL
                color=discord.Color.green() # Change color back to green
            )

            # Add fields with current data (no strikethrough)
            embed.add_field(name="Adress", value=f"```{listing.get('address', 'N/A')}```", inline=False)
            embed.add_field(name="Rum", value=f"```{listing.get('rooms', 'N/A')}```", inline=True)
            embed.add_field(name="Storlek", value=f"```{listing.get('size', 'N/A')}```", inline=True)
            embed.add_field(name="Hyra", value=f"```{listing.get('price', 'N/A')}```", inline=True)
            embed.add_field(name="Ledigt", value=f"```{listing.get('available', 'N/A')}```", inline=False)

            # Set image if URL is provided
            if listing.get('image_url'):
                embed.set_image(url=listing.get('image_url'))
                print(f"Setting image for reactivated listing: {listing['image_url']}")

            # Edit the message with the new embed
            await message.edit(embed=embed)
            print(f"Successfully updated reactivated listing message for: {listing.get('address', 'Unknown')}")
        except discord.errors.NotFound:
             print(f"Message with ID {listing['message_id']} not found for reactivated listing: {listing.get('address', 'Unknown')}")
        except Exception as e:
            print(f"Error updating reactivated listing message for {listing.get('address', 'Unknown')}: {e}")


    async def clear_messages(self, listings):
        await self.ensure_connected()
        deleted_count = 0

        # Collect all message IDs first
        message_ids = [(listing.get('message_id'), listing) for listing in listings if listing.get('message_id')]
        print(f"Found {len(message_ids)} message IDs to delete")

        for msg_id, listing in message_ids:
            if msg_id: # Ensure msg_id is not None
                try:
                    # Fetch and delete the message
                    message = await self.channel.fetch_message(msg_id)
                    await message.delete()
                    deleted_count += 1
                    print(f"Deleted message ID {msg_id} for: {listing.get('address', 'Unknown')} | {listing.get('size', 'N/A')} | {listing.get('rooms', 'N/A')}")

                except discord.errors.NotFound:
                    print(f"Message with ID {msg_id} not found for deletion (already deleted?): {listing.get('address', 'Unknown')}")
                except Exception as e:
                    print(f"Failed to delete message with ID {msg_id} for {listing.get('address', 'Unknown')}: {e}")

        # Clear message IDs from listings data in memory
        for listing in listings:
            if 'message_id' in listing:
                del listing['message_id']
            if 'channel_id' in listing:
                del listing['channel_id']

        # Write updated listings (without message IDs) back to JSON
        # This happens in the main execution block after the clear operation completes.
        return deleted_count

    async def close(self):
        # Close the Discord client connection
        if self.client and not self.client.is_closed():
            await self.client.close()

async def handle_discord_operations(new_listings=None, removed_listings=None, reactivated_listings=None):
    # Create a DiscordNotifier instance
    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)

    # Use a try...finally block to ensure the client is closed
    try:
        # Ensure the bot is connected before processing notifications
        await notifier.ensure_connected()
        print(f"\nProcessing Discord notifications:")

        # Send notifications for new listings
        if new_listings:
            print(f"Sending {len(new_listings)} new listings...")
            for listing in new_listings:
                print(f"Sending notification for: {listing.get('address', 'Unknown')} | {listing.get('size', 'N/A')} | {listing.get('rooms', 'N/A')}")
                # send_notification updates the listing object with message_id and channel_id
                await notifier.send_notification(listing)
                # Add a small delay to avoid hitting Discord rate limits
                await asyncio.sleep(1)

        # Update messages for reactivated listings
        if reactivated_listings:
            print(f"Updating {len(reactivated_listings)} reactivated listings...")
            for listing in reactivated_listings:
                 print(f"Updating reactivated listing message for: {listing.get('address', 'Unknown')}")
                 await notifier.update_reactivated_listing(listing)
                 # Add a small delay
                 await asyncio.sleep(1)

        # Update messages for removed listings
        if removed_listings:
            print(f"Updating {len(removed_listings)} removed listings...")
            for listing in removed_listings:
                print(f"Updating removed listing message for: {listing.get('address', 'Unknown')}")
                await notifier.update_removed_listing(listing)
                # Add a small delay
                await asyncio.sleep(1)

    except Exception as e:
        print(f"Error in Discord operations: {e}")
    finally:
        # Ensure the Discord client is closed after operations
        await notifier.close()


def scrape_all_sites(existing_listings, scrapers):
    print(f"\nStarting scrape with {len(existing_listings)} existing listings")
    all_listings = []
    all_new = []
    all_removed = []
    all_reactivated = []

    # Iterate through each scraper
    for scraper in scrapers:
        print(f"\nRunning {scraper.__class__.__name__}")
        # Call the scraper's scrape method, passing the existing listings
        # The scraper is responsible for comparing current scrape results
        # against existing_listings to determine new, removed, and reactivated.
        listings, new, removed, reactivated = scraper.scrape(existing_listings)
        # Extend the main lists with results from the current scraper
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

    # Load existing listings from the JSON file at the start of the script
    existing_listings = []
    if os.path.exists(OUTPUT_JSON_FILE):
        try:
            with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                # Load existing listings, handling potential empty file
                file_content = f.read()
                if file_content:
                    existing_listings = json.loads(file_content)
                else:
                    existing_listings = [] # Initialize as empty list if file is empty
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {OUTPUT_JSON_FILE}. Starting with empty listings.")
            existing_listings = [] # Initialize as empty list on error
        except Exception as e:
            print(f"Error loading {OUTPUT_JSON_FILE}: {e}. Starting with empty listings.")
            existing_listings = [] # Initialize as empty list on other errors

    # Handle the --clear argument to delete Discord messages and clear the JSON file
    if args.clear:
        if os.path.exists(OUTPUT_JSON_FILE):
            try:
                # Load current listings to get message IDs before clearing
                with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as f:
                     # Load existing listings, handling potential empty file
                    file_content = f.read()
                    if file_content:
                        listings_to_clear = json.loads(file_content)
                    else:
                        listings_to_clear = []

                if listings_to_clear:
                    print(f"Clearing {len(listings_to_clear)} messages...")
                    notifier = DiscordNotifier(DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID)

                    async def run_clear():
                        await notifier.ensure_connected()
                        deleted = await notifier.clear_messages(listings_to_clear)
                        await notifier.close()
                        return deleted

                    # Run the async clear operation
                    deleted_count = asyncio.run(run_clear())
                    print(f"Successfully deleted {deleted_count} messages")

                # After attempting to delete messages, empty the JSON file
                with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                    print(f"Successfully emptied {OUTPUT_JSON_FILE}")

            except Exception as e:
                print(f"Error during clear operation: {e}")
        else:
            print(f"{OUTPUT_JSON_FILE} not found, no messages to clear.")
        exit(0) # Exit after clear operation

    # Handle debug mode (simulating removed listings)
    if args.debug:
        # In debug mode with --remove, we modify the existing listings directly
        all_listings = []
        # Copy listings while preserving message_id for potential updates
        for listing in existing_listings:
            new_listing = listing.copy()
            if 'message_id' in listing:
                new_listing['message_id'] = listing['message_id']
            all_listings.append(new_listing)

        newly_found_listings = []
        removed_listings = []
        reactivated = [] # Initialize reactivated list for debug mode

        if args.remove:
            # Find and mark the listing as inactive in the copied list
            found_and_removed = False
            for listing in all_listings:
                if listing.get('address') == args.remove: # Use .get for safety
                    listing['active'] = False
                    listing['removed_at'] = datetime.now().strftime("%Y-%m-%d")
                    removed_listings.append(listing)
                    found_and_removed = True
                    print(f"Simulating removal of listing: {args.remove}")
                    break
            if not found_and_removed:
                 print(f"Warning: Listing with address '{args.remove}' not found for removal simulation.")

        # In debug mode without --remove, all existing listings are treated as current,
        # and no new/removed/reactivated lists are generated by scraping.
        # If you need to simulate new listings in debug, you would add them here.

    # Normal scraping mode
    else:
        active_scrapers = get_active_scrapers(args)
        # Perform the actual scraping and comparison
        all_listings, newly_found_listings, removed_listings, reactivated = scrape_all_sites(
            existing_listings, # Pass existing listings to the scraper functions
            active_scrapers
        )

    # After scraping (or debug simulation), write the complete list of current listings to JSON
    # This includes all active listings and any marked as inactive/removed in this run.
    if all_listings is not None: # Ensure all_listings is not None before writing
        try:
            with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(all_listings, f, indent=2, ensure_ascii=False)
            print(f"Successfully wrote {len(all_listings)} listings to {OUTPUT_JSON_FILE}")
        except Exception as e:
            print(f"Error writing to {OUTPUT_JSON_FILE}: {e}")

    # Handle Discord notifications for changes detected
    # Only run Discord operations if there are changes to report
    if removed_listings or newly_found_listings or reactivated:
        try:
            # Run the asynchronous Discord operations
            asyncio.run(handle_discord_operations(
                new_listings=newly_found_listings,
                removed_listings=removed_listings,
                reactivated_listings=reactivated
            ))
        except Exception as e:
            print(f"An error occurred during Discord operations: {e}")

    # Note: The script finishes here. The workflow will then upload the updated listings.json.
