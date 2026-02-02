"""Utility functions for the homelab Discord bot."""

import json
import logging
import os

from .config import COUNTER_STATE_FILE, DASHBOARD_STATE_FILE

logger = logging.getLogger("discord_bot")


def format_uptime(uptime_seconds):
    """Format uptime into a human-readable string with appropriate units."""
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)

    result = ""
    if days > 0:
        result += f"{days}d "
    result += f"{hours}h {minutes}m {seconds}s"

    logger.debug(
        f"UPTIME CONVERSION: seconds={uptime_seconds}, formatted as: {days}d {hours}h {minutes}m {seconds}s"
    )
    return result


def save_dashboard_state(channel_id, message_id):
    """Save the dashboard state to a file."""
    try:
        state = {"channel_id": channel_id, "message_id": message_id}
        os.makedirs(os.path.dirname(DASHBOARD_STATE_FILE), exist_ok=True)
        with open(DASHBOARD_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error saving dashboard state: {e}")


def load_dashboard_state():
    """Load the dashboard state from file."""
    try:
        if os.path.exists(DASHBOARD_STATE_FILE):
            with open(DASHBOARD_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading dashboard state: {e}")
    return None


def load_request_counter():
    """Load the request counter from file."""
    try:
        if os.path.exists(COUNTER_STATE_FILE):
            with open(COUNTER_STATE_FILE, "r") as f:
                state = json.load(f)
                return state.get("counter", 0)
    except Exception as e:
        print(f"Error loading request counter: {e}")
    return 0


def save_request_counter(counter):
    """Save the request counter to a file."""
    try:
        state = {"counter": counter}
        os.makedirs(os.path.dirname(COUNTER_STATE_FILE), exist_ok=True)
        with open(COUNTER_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error saving request counter: {e}")
