import os
import sys
from pathlib import Path

# Try environment variables first
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = os.environ.get('DISCORD_CHANNEL_ID')

# If not found in environment, try app_secrets.py
if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
    try:
        from app_secrets import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
    except ImportError:
        print("Error: Discord credentials not found!")
        print("Please either:")
        print("1. Set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID environment variables")
        print("2. Create a app_secrets.py file with these variables")
        sys.exit(1)

# Convert channel ID to int
try:
    DISCORD_CHANNEL_ID = int(DISCORD_CHANNEL_ID)
except (ValueError, TypeError):
    print("Error: DISCORD_CHANNEL_ID must be a valid integer")
    sys.exit(1)