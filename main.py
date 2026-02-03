"""Entry point for the homelab Discord bot."""

from src import config
from src.bot import bot

# Load extensions (registers commands)
import src.extensions  # noqa: F401

# Load events (registers event handlers)
import src.events  # noqa: F401


def main():
    """Start the bot."""
    if not config.TOKEN:
        print("❌ Error: DISCORD_TOKEN is not set")
        return
    if not config.TEST_GUILD_ID:
        print("❌ Error: TEST_GUILD_ID is not set")
        return
    if config.MEDIA_VOTES_DRY_RUN:
        print("⚠️  Media votes DRY RUN enabled - no files will be deleted")
    bot.run(config.TOKEN)


if __name__ == "__main__":
    main()
