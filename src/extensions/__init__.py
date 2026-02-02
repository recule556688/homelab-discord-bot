"""Extensions package - loads all bot extensions."""

# Import order matters for registration
from . import dashboard
from . import system
from . import plex
from . import overseerr
from . import onboarding
from . import permissions
from . import server_setup

__all__ = [
    "dashboard",
    "system",
    "plex",
    "overseerr",
    "onboarding",
    "permissions",
    "server_setup",
]
