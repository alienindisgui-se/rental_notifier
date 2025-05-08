import discord
from discord.ext import commands
from config import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID

# Use the token from config
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user.name} ({bot.user.id})')
    print(f'👀 Watching channel ID: {DISCORD_CHANNEL_ID}')

@bot.command()
@commands.has_permissions(administrator=True)
async def purge(ctx, amount: str = None):
    if ctx.channel.id != DISCORD_CHANNEL_ID:
        await ctx.send("❌ This command can only be used in the designated channel.")
        return

    if amount is None:
        await ctx.send("❌ Please specify a number or 'all'.")
        return

    if amount.lower() == 'all':
        deleted = await ctx.channel.purge(limit=None)
        await ctx.send(f'✅ Deleted {len(deleted)} messages.', delete_after=5)
        return

    try:
        amount = int(amount)
        if amount < 1 or amount > 100:
            await ctx.send("❌ Please choose a number between 1 and 100 or use 'all'.")
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f'✅ Deleted {len(deleted)} messages.', delete_after=5)
    except ValueError:
        await ctx.send("❌ Please provide a valid number or 'all'.")

@purge.error
async def purge_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need administrator permissions to use this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Usage: `!purge <number|all>`")

bot.run(DISCORD_BOT_TOKEN)
