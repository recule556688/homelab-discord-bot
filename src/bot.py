"""Discord bot instance and command tree."""

import discord
import logging
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.DEBUG)

logger.info("Bot starting up...")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
