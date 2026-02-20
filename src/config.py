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

# Radarr / Sonarr (for media deletion)
RADARR_URL = os.getenv("RADARR_URL")
RADARR_API_KEY = os.getenv("RADARR_API_KEY")
SONARR_URL = os.getenv("SONARR_URL")
SONARR_API_KEY = os.getenv("SONARR_API_KEY")
VOTE_DURATION_DAYS = int(os.getenv("VOTE_DURATION_DAYS", "7"))
AUTO_VOTE_UNWATCHED_DAYS = int(os.getenv("AUTO_VOTE_UNWATCHED_DAYS", "90"))
VOTE_CHANNEL_ID = int(os.getenv("VOTE_CHANNEL_ID", "0")) or None
VOTE_MENTION_ROLE_ID = int(os.getenv("VOTE_MENTION_ROLE_ID", "0")) or None
MEDIA_VOTES_DRY_RUN = os.getenv("MEDIA_VOTES_DRY_RUN", "").lower() in ("1", "true", "yes")

# File paths - use project root (parent of src/) for data/
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_STATE_FILE = os.path.join(_BASE_DIR, "data", "dashboard_state.json")
COUNTER_STATE_FILE = os.path.join(_BASE_DIR, "data", "counter_state.json")
USER_MAPPING_FILE = os.path.join(_BASE_DIR, "data", "overseerr_users.json")
MEDIA_VOTES_FILE = os.path.join(_BASE_DIR, "data", "media_votes.json")
MEDIA_VOTES_PROPOSED_FILE = os.path.join(_BASE_DIR, "data", "media_votes_proposed.json")
AUTO_VOTE_LAST_RUN_FILE = os.path.join(_BASE_DIR, "data", "auto_vote_last_run.json")

# Admin commands (for permission checks)
ADMIN_COMMANDS = [
    "setup_homelab",
    "sync",
    "fix_permissions",
    "fix_thread_permissions",
    "fix_access_channel",
    "send_intro_embed",
    "send_invite_embed",
    "vote_delete",
    "cancel_vote",
    "cancel_all_votes",
    "finish_vote",
    "start_media_vote",
]

# Role IDs
NEWBIE_ROLE_ID = 1362860764091908367
