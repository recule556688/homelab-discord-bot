"""Configuration and constants for the homelab Discord bot."""

import os
from dotenv import load_dotenv

load_dotenv()

# Discord
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID")) if os.getenv("TEST_GUILD_ID") else None

# Plex
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

# Overseerr
OVERSEERR_URL = os.getenv("OVERSEERR_URL", "https://overseer.tessdev.fr")
OVERSEERR_API_KEY = os.getenv("OVERSEERR_API_KEY")

# File paths - use project root (parent of src/) for data/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_STATE_FILE = os.path.join(_BASE_DIR, "data", "dashboard_state.json")
COUNTER_STATE_FILE = os.path.join(_BASE_DIR, "data", "counter_state.json")
USER_MAPPING_FILE = os.path.join(_BASE_DIR, "data", "overseerr_users.json")

# Admin commands (for permission checks)
ADMIN_COMMANDS = [
    "setup_homelab",
    "sync",
    "fix_permissions",
    "fix_thread_permissions",
    "fix_access_channel",
    "send_intro_embed",
    "send_invite_embed",
]

# Role IDs
NEWBIE_ROLE_ID = 1362860764091908367
