import os

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.environ.get('DISCORD_CHANNEL_ID', 0))

if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
    try:
        from .secrets import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
    except ImportError:
        raise ValueError("Discord credentials not found in environment variables or secrets.py")