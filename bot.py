import os
import time
import psutil
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import json
from plexapi.server import PlexServer
from datetime import datetime, timedelta
from discord.ui import Button, View
import asyncio

# Load settings from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID"))
PLEX_URL = os.getenv("PLEX_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")

# Set up the bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Global variables to store the dashboard embed message and the channel it's in.
dashboard_message = None
dashboard_channel = None

# File to store dashboard state
DASHBOARD_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dashboard_state.json")

# Add a constant for the counter state file
COUNTER_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "counter_state.json")

def get_plex_connection():
    """Create a connection to Plex server"""
    try:
        return PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None

def save_dashboard_state(channel_id, message_id):
    """Save the dashboard state to a file"""
    try:
        state = {
            "channel_id": channel_id,
            "message_id": message_id
        }
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(DASHBOARD_STATE_FILE), exist_ok=True)
        with open(DASHBOARD_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error saving dashboard state: {e}")

def load_dashboard_state():
    """Load the dashboard state from file"""
    try:
        if os.path.exists(DASHBOARD_STATE_FILE):
            with open(DASHBOARD_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading dashboard state: {e}")
    return None

def create_health_embed():
    # Calculate uptime (since system boot) formatted as h m s.
    uptime_seconds = time.time() - psutil.boot_time()
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    # Gather CPU and RAM usage using psutil
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Get network info with error handling
    try:
        net_io = psutil.net_io_counters()
        net_bytes_sent = net_io.bytes_sent / (1024**2)  # Convert to MB
        net_bytes_recv = net_io.bytes_recv / (1024**2)  # Convert to MB
    except:
        net_bytes_sent = 0
        net_bytes_recv = 0

    # Build the embed with modern styling
    embed = discord.Embed(
        title="",
        description="",
        color=0x00b8ff  # Plex blue color
    )

    # Title
    embed.add_field(
        name="\n💻 LIVE SYSTEM DASHBOARD 📊",
        value="━━━━━━━━━━━━━━━━━━━━━━━━",
        inline=False
    )

    # System Overview
    system_stats = (
        f"```ansi\n"
        f"\u001b[1;36mSYSTEM OVERVIEW\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ Uptime: \u001b[1;33m{uptime_str}\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=system_stats, inline=False)

    # Resource Usage
    resource_stats = (
        f"```ansi\n"
        f"\u001b[1;35mRESOURCE USAGE\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ CPU: \u001b[1;{33 if cpu_usage < 80 else 31}m{cpu_usage}%\u001b[0m\n"
        f"│ RAM: \u001b[1;{33 if memory.percent < 80 else 31}m{memory.percent}%\u001b[0m\n"
        f"│ Used: \u001b[1;36m{memory.used / (1024**3):.1f}GB\u001b[0m / \u001b[1;33m{memory.total / (1024**3):.1f}GB\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=resource_stats, inline=True)

    # Network Status
    network_stats = (
        f"```ansi\n"
        f"\u001b[1;35mNETWORK STATUS\u001b[0m\n"
        f"┌──────────────────────────┐\n"
        f"│ Upload: \u001b[1;32m{net_bytes_sent:.1f} MB\u001b[0m\n"
        f"│ Download: \u001b[1;32m{net_bytes_recv:.1f} MB\u001b[0m\n"
        f"└──────────────────────────┘\n"
        f"```"
    )
    embed.add_field(name="", value=network_stats, inline=True)

    # Add timestamp and refresh info
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(
        text=f"🔄 Auto-updates every 30s • Last update: {current_time}",
        icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png"
    )

    return embed


@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")
    try:
        # Set status to DND with a custom activity
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="You and all your hardware 😏"
            )
        )
        # Get the test guild
        guild = discord.Object(id=TEST_GUILD_ID)
        # Sync the commands
        synced = await tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {TEST_GUILD_ID}")
        # Restore dashboard if it exists
        state = load_dashboard_state()
        if state:
            try:
                channel = await bot.fetch_channel(state["channel_id"])
                message = await channel.fetch_message(state["message_id"])
                global dashboard_message, dashboard_channel
                dashboard_message = message
                dashboard_channel = channel
                if not update_dashboard.is_running():
                    update_dashboard.start()
                print("✅ Restored dashboard state")
            except discord.NotFound:
                print("❌ Could not restore dashboard - message or channel not found")
                # Clean up invalid state
                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.event
async def on_member_join(member):
    try:
        # Use the specific Newbie role ID
        NEWBIE_ROLE_ID = 1362860764091908367
        newbie_role = member.guild.get_role(NEWBIE_ROLE_ID)
        
        if newbie_role:
            await member.add_roles(newbie_role)
            print(f"✅ Added Newbie role to {member.name}")
            
            # Optional: Send a welcome message
            welcome_channel = discord.utils.get(member.guild.channels, name="📖｜start-here")
            if welcome_channel:
                await welcome_channel.send(f"Welcome {member.mention}! You've been assigned the {newbie_role.name} role.")
        else:
            print(f"❌ Could not find Newbie role with ID {NEWBIE_ROLE_ID}")
            
    except Exception as e:
        print(f"❌ Error assigning Newbie role to {member.name}: {e}")

# Define which commands should be restricted to admins
ADMIN_COMMANDS = [
    "setup_homelab",
    "sync",
    "fix_permissions",
    "fix_thread_permissions",
    "fix_access_channel",
    "send_intro_embed",
    "send_invite_embed"
]

# When setting up commands, set default permissions
async def setup_commands():
    """Set up all slash commands"""
    guild = discord.Object(id=TEST_GUILD_ID)
    
    # Commands list
    commands = [
        app_commands.Command(
            name="setup_homelab",
            description="Set up the homelab server layout with roles and channels.",
            callback=setup_homelab,
            default_permissions=discord.Permissions(administrator=True)  # Only visible to admins
        ),
        app_commands.Command(
            name="dashboard",
            description="Start a persistent server health dashboard.",
            callback=dashboard
        ),
        app_commands.Command(
            name="sync",
            description="Sync slash commands (Admin only)",
            callback=sync,
            default_permissions=discord.Permissions(administrator=True)
        ),
        app_commands.Command(
            name="fix_permissions",
            description="Fix permissions for all roles and channels",
            callback=fix_permissions,
            default_permissions=discord.Permissions(administrator=True)
        ),
        app_commands.Command(
            name="send_intro_embed",
            description="Send the onboarding embed to the start-here channel.",
            callback=send_intro_embed,
            default_permissions=discord.Permissions(administrator=True)
        ),
        app_commands.Command(
            name="send_invite_embed",
            description="Send the get-invite embed to the channel.",
            callback=send_invite_embed,
            default_permissions=discord.Permissions(administrator=True)
        ),
        # Normal user commands
        app_commands.Command(
            name="serverhealth",
            description="Check current server health stats.",
            callback=server_health
        ),
        app_commands.Command(
            name="ping",
            description="Check the bot's latency.",
            callback=ping
        ),
        app_commands.Command(
            name="commands",
            description="List all available commands",
            callback=list_commands
        ),
        app_commands.Command(
            name="media_stats",
            description="Show statistics for Movies, TV Shows, Anime Shows, and Anime Movies",
            callback=media_stats
        ),
        app_commands.Command(
            name="restrict_channels",
            description="Strictly restrict channel visibility for new users",
            callback=restrict_channels,
            default_permissions=discord.Permissions(administrator=True)
        )
    ]
    
    # Add each command to the tree
    for cmd in commands:
        tree.add_command(cmd, guild=guild)


@tree.command(
    name="dashboard",
    description="Start a persistent server health dashboard.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def dashboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    try:
        global dashboard_message, dashboard_channel

        # Delete existing dashboard if it exists
        try:
            state = load_dashboard_state()
            if state:
                try:
                    old_channel = await bot.fetch_channel(state["channel_id"])
                    old_message = await old_channel.fetch_message(state["message_id"])
                    await old_message.delete()
                except:
                    pass  # Ignore if message doesn't exist or can't be deleted
                
                # Clean up the state file
                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)
        except:
            pass  # Ignore any errors during cleanup

        dashboard_channel = interaction.channel

        # Send an ephemeral message so the user knows the dashboard is starting
        await interaction.followup.send(
            "🚀 Starting system dashboard... (This message will disappear)", 
            ephemeral=True
        )

        # Post the first dashboard embed publicly
        embed = create_health_embed()
        dashboard_message = await dashboard_channel.send(embed=embed)

        # Save the dashboard state
        save_dashboard_state(dashboard_channel.id, dashboard_message.id)

        # Start the background update loop if it isn't running already
        if not update_dashboard.is_running():
            update_dashboard.start()

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to start dashboard:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tasks.loop(seconds=30)
async def update_dashboard():
    global dashboard_message
    if dashboard_message:
        try:
            new_embed = create_health_embed()
            await dashboard_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            # If we lost the message reference, try to restore it
            try:
                state = load_dashboard_state()
                if state:
                    channel = await bot.fetch_channel(state["channel_id"])
                    dashboard_message = await channel.fetch_message(state["message_id"])
                    await dashboard_message.edit(embed=new_embed)
            except Exception as restore_error:
                print(f"Failed to restore dashboard: {restore_error}")


@tree.command(
    name="serverhealth",
    description="Check current server health stats.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def server_health(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # System uptime
        uptime_seconds = time.time() - psutil.boot_time()
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

        # CPU information
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        cpu_temp = None
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if "coretemp" in temps:
                    cpu_temp = max(temp.current for temp in temps["coretemp"])
        except:
            cpu_temp = "N/A"

        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Network information - handle permissions gracefully
        try:
            net_io = psutil.net_io_counters()
            net_bytes_sent = net_io.bytes_sent
            net_bytes_recv = net_io.bytes_recv
            try:
                net_connections = len(psutil.net_connections())
            except (psutil.AccessDenied, PermissionError):
                net_connections = "N/A (Permission denied)"
        except Exception:
            net_bytes_sent = 0
            net_bytes_recv = 0
            net_connections = "N/A"

        # Build the embed with a modern layout
        embed = discord.Embed(
            title="",
            description="",
            color=0x00b8ff
        )

        # Modern title with emoji
        embed.add_field(
            name="\n💻 SYSTEM HEALTH DASHBOARD 📊",
            value="━━━━━━━━━━━━━━━━━━━━━━━━",
            inline=False
        )

        # System Stats
        system_stats = (
            f"```ansi\n"
            f"\u001b[1;36mSYSTEM OVERVIEW\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Uptime: \u001b[1;33m{uptime_str}\u001b[0m\n"
            f"│ CPU Cores: \u001b[1;33m{cpu_count}\u001b[0m\n"
            f"│ CPU Freq: \u001b[1;33m{cpu_freq.current:.0f}MHz\u001b[0m\n"
            f"│ Temperature: \u001b[1;33m{cpu_temp if cpu_temp else 'N/A'}°C\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=system_stats, inline=False)

        # Resource Usage
        resource_stats = (
            f"```ansi\n"
            f"\u001b[1;35mRESOURCE USAGE\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ CPU: \u001b[1;{33 if cpu_usage < 80 else 31}m{cpu_usage}%\u001b[0m\n"
            f"│ RAM: \u001b[1;{33 if memory.percent < 80 else 31}m{memory.percent}%\u001b[0m ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)\n"
            f"│ Swap: \u001b[1;{33 if swap.percent < 80 else 31}m{swap.percent}%\u001b[0m ({swap.used / (1024**3):.1f}GB / {swap.total / (1024**3):.1f}GB)\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=resource_stats, inline=True)

        # Network Stats
        network_stats = (
            f"```ansi\n"
            f"\u001b[1;35mNETWORK STATUS\u001b[0m\n"
            f"┌──────────────────────────┐\n"
            f"│ Connections: \u001b[1;33m{net_connections}\u001b[0m\n"
            f"│ Sent: \u001b[1;36m{net_bytes_sent / (1024**2):.1f}MB\u001b[0m\n"
            f"│ Received: \u001b[1;36m{net_bytes_recv / (1024**2):.1f}MB\u001b[0m\n"
            f"└──────────────────────────┘\n"
            f"```"
        )
        embed.add_field(name="", value=network_stats, inline=True)

        # Add timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /serverhealth to refresh",
            icon_url="https://cdn.iconscout.com/icon/free/png-256/refresh-1781197-1518571.png"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch server health:\n```ansi\n\u001b[1;31m{str(e)}\u001b[0m```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


@tree.command(
    name="ping",
    description="Check the bot's latency.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {latency}ms", ephemeral=True
    )


@tree.command(
    name="setup_homelab",
    description="Set up the homelab server layout with roles and channels.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_homelab(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild

    # Define roles with their permissions
    roles = {
        "🛡️ Admin": discord.Permissions(administrator=True),
        "👀 Observer": discord.Permissions(view_channel=True),
        "🔧 Maintainer": discord.Permissions(manage_messages=True),
        "🤖 Bot": discord.Permissions(
            # General Permissions
            view_channel=True,
            send_messages=True,
            send_messages_in_threads=True,
            create_public_threads=True,
            create_private_threads=True,
            manage_threads=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            mention_everyone=True,
            use_external_emojis=True,
            add_reactions=True,
            # Role Management
            manage_roles=True,
            # Channel Management
            manage_channels=True,
            # Message Management
            manage_messages=True,
            # Member Management
            moderate_members=True,
        ),
        "🎮 Gamer": discord.Permissions(read_messages=True),
        "🎟️ Approved": discord.Permissions(read_messages=True),
        "⏳ Pending": discord.Permissions(read_messages=True),
        "❌ Denied": discord.Permissions(read_messages=True),
    }

    # Create or update roles
    for name, perms in roles.items():
        existing_role = discord.utils.get(guild.roles, name=name)
        if not existing_role:
            await guild.create_role(name=name, permissions=perms)
            print(f"Created role: {name}")

    # Define categories and their channels
    categories = {
        "📊 System & Status": [
            "📈｜system-health",
            "📦｜docker-containers",
            "🕒｜uptime-status",
            "🧰｜maintenance-log",
        ],
        "📽️ Media Center": [
            "🎬｜radarr-status",
            "📺｜sonarr-status",
            "🎶｜lidarr-status",
            "📤｜download-queue",
            "🧞｜overseerr-requests",
        ],
        "🎮 Game Servers": [
            "🎮｜server-status",
            "⚙️｜console-logs",
            "👥｜player-activity",
            "📌｜how-to-join",
        ],
        "🛰️ Overseerr & Requests": [
            "📥｜new-requests",
            "✅｜approved-downloads",
            "❌｜rejected-requests",
        ],
        "🤖 Bot Commands": ["🤖｜commands", "📜｜logs", "🔒｜admin-cmds"],
        "🚨 Alerts": ["🔥｜alerts", "👀｜watchdog"],
        "👋 Onboarding": [  # New category for onboarding
            "📖｜start-here",
            "📬｜get-invite",
            "🎫｜access-requests",
        ],
    }

    # Create or update categories and channels
    for category_name, channels in categories.items():
        # Check if category exists
        existing_category = discord.utils.get(guild.categories, name=category_name)
        if not existing_category:
            category = await guild.create_category(category_name)
            print(f"Created category: {category_name}")
        else:
            category = existing_category
            print(f"Using existing category: {category_name}")

        # Create or update channels in the category
        for channel_name in channels:
            existing_channel = discord.utils.get(guild.channels, name=channel_name)
            if not existing_channel:
                # Set up channel permissions based on category
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(
                        # Basic permissions
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        # Thread permissions
                        create_public_threads=True,
                        create_private_threads=True,
                        send_messages_in_threads=True,
                        manage_threads=True,
                        # Message permissions
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True,
                        add_reactions=True,
                        # Role management
                        manage_roles=True,
                    ),
                }
                
                # Special permissions for onboarding channels
                if category_name == "👋 Onboarding":
                    if channel_name == "📖｜start-here":
                        # Everyone can read start-here
                        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=True)
                    elif channel_name == "📬｜get-invite":
                        # Only approved users can see get-invite
                        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")
                        if approved_role:
                            overwrites[approved_role] = discord.PermissionOverwrite(read_messages=True)
                    elif channel_name == "🎫｜access-requests":
                        # Only mods and admins can see access requests
                        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
                        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
                        if admin_role:
                            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True)
                        if maintainer_role:
                            overwrites[maintainer_role] = discord.PermissionOverwrite(read_messages=True)

                await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
                print(f"Created channel: {channel_name}")

    await interaction.followup.send("🎉 Server structure created/updated successfully!")


@tree.command(
    name="sync",
    description="Sync slash commands (Admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    """Manually sync slash commands"""
    await interaction.response.defer(ephemeral=True)
    try:
        # Sync to test guild
        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        await interaction.followup.send(
            f"✅ Successfully synced {len(synced)} commands to guild {TEST_GUILD_ID}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to sync commands: {e}",
            ephemeral=True
        )


@tree.command(
    name="commands",
    description="List all available commands",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def list_commands(interaction: discord.Interaction):
    """List all available commands with their descriptions"""
    commands_list = []
    for cmd in tree.get_commands(guild=discord.Object(id=TEST_GUILD_ID)):
        commands_list.append(f"`/{cmd.name}` - {cmd.description}")
    embed = discord.Embed(
        title="🤖 Available Commands",
        description="\n".join(commands_list),
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(
    name="media_stats",
    description="Show statistics for Movies, TV Shows, Anime Shows, and Anime Movies",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def media_stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    plex = get_plex_connection()
    if not plex:
        await interaction.followup.send("❌ Could not connect to Plex server. Please check your configuration.", ephemeral=True)
        return

    try:
        # Initialize the embed
        embed = discord.Embed(
            title="📊 Media Library Statistics",
            description="Statistics from your Plex Libraries",
            color=0x1f2033  # Dark blue background
        )

        # Define specific libraries to process
        library_names = ["Movies", "TV Shows", "Anime Shows", "Anime Movies"]
        library_stats = {}
        recent_items = []
        
        # Track overall totals
        total_items = 0
        total_size_gb = 0
        total_duration_minutes = 0
        total_episodes = 0
        recent_date = datetime.now() - timedelta(days=7)
        
        # Process each specific library
        for library_name in library_names:
            try:
                library = plex.library.section(library_name)
                library_items = library.all()
                item_count = len(library_items)
                total_items += item_count
                
                # Calculate size and duration
                library_size_gb = 0
                duration_minutes = 0
                recent_count = 0
                episode_count = 0
                
                # Process based on whether it's movies or shows
                if "movie" in library_name.lower():
                    # Movie libraries
                    for movie in library_items:
                        # Size
                        if hasattr(movie, 'media') and movie.media:
                            library_size_gb += movie.media[0].parts[0].size / (1024**3)  # Convert to GB
                        # Duration
                        if hasattr(movie, 'duration'):
                            duration_minutes += movie.duration / 60000  # Convert ms to minutes
                        # Recent items
                        if hasattr(movie, 'addedAt') and movie.addedAt >= recent_date:
                            recent_count += 1
                            recent_items.append((movie.title, library_name, movie.year, movie.addedAt))
                            
                    # Calculate days, hours, minutes
                    days = int(duration_minutes // 1440)
                    hours = int((duration_minutes % 1440) // 60)
                    minutes = int(duration_minutes % 60)
                    
                    # Add to library stats
                    library_stats[library_name] = {
                        "count": item_count,
                        "size_gb": library_size_gb,
                        "duration": f"{days}d {hours}h {minutes}m",
                        "duration_minutes": duration_minutes,
                        "recent_count": recent_count,
                        "type": "movie"
                    }
                    
                elif "show" in library_name.lower():
                    # TV Shows libraries
                    for show in library_items:
                        # Process episodes
                        episodes = show.episodes()
                        episode_count += len(episodes)
                        for episode in episodes:
                            # Size
                            if hasattr(episode, 'media') and episode.media:
                                library_size_gb += episode.media[0].parts[0].size / (1024**3)  # Convert to GB
                            # Duration
                            if hasattr(episode, 'duration'):
                                duration_minutes += episode.duration / 60000  # Convert ms to minutes
                        # Recent items
                        if hasattr(show, 'addedAt') and show.addedAt >= recent_date:
                            recent_count += 1
                            recent_items.append((show.title, library_name, len(episodes), show.addedAt))
                    
                    # Calculate days, hours, minutes
                    days = int(duration_minutes // 1440)
                    hours = int((duration_minutes % 1440) // 60)
                    minutes = int(duration_minutes % 60)
                    
                    # Add to library stats
                    library_stats[library_name] = {
                        "count": item_count,
                        "episodes": episode_count,
                        "size_gb": library_size_gb,
                        "duration": f"{days}d {hours}h {minutes}m",
                        "duration_minutes": duration_minutes,
                        "recent_count": recent_count,
                        "type": "show"
                    }
                
                # Add to totals
                total_size_gb += library_size_gb
                total_duration_minutes += duration_minutes
                total_episodes += episode_count
                
            except Exception as e:
                # If processing a library fails, record the error
                embed.add_field(
                    name=f"❌ Error processing {library_name}",
                    value=f"Error: {str(e)}",
                    inline=False
                )
        
        # Calculate total duration
        total_days = int(total_duration_minutes // 1440)
        total_hours = int((total_duration_minutes % 1440) // 60)
        total_minutes = int(total_duration_minutes % 60)
        
        # Add total stats with ansi colors
        total_stats = (
            f"```ansi\n"
            f"\u001b[1;36m🎬 TOTAL COLLECTION\u001b[0m\n\n"
            f"┌─────────────────────────\n"
            f"│ Duration: \u001b[1;33m{total_days}d {total_hours}h {total_minutes}m\u001b[0m\n"
            f"│ Size: \u001b[1;33m{total_size_gb:.1f}GB\u001b[0m\n"
            f"└─────────────────────────\n"
            f"```"
        )
        embed.add_field(name="", value=total_stats, inline=False)
        
        # Add library-specific stats with ansi colors
        for name, stats in library_stats.items():
            if stats["type"] == "movie":
                if name == "Movies":
                    emoji = "🎬"
                    display_name = "MOVIES"
                    color = "35"  # Purple
                else:  # Anime Movies
                    emoji = "🇯🇵"
                    display_name = "ANIME MOVIES"
                    color = "35;1"  # Bright purple
                
                lib_stats = (
                    f"```ansi\n"
                    f"\u001b[1;{color}m{emoji} {display_name}\u001b[0m\n\n"
                    f"┌───────────────\n"
                    f"│ Total: \u001b[1;33m{stats['count']} \u001b[0m"
                    f"\u001b[33mmovies\u001b[0m\n"
                    f"│ Duration: \u001b[1;36m{stats['duration']}\u001b[0m\n"
                    f"│ Size: \u001b[1;36m{stats['size_gb']:.1f}GB\u001b[0m\n"
                    f"│ Average: \u001b[1;32m{(stats['duration_minutes'] / stats['count'] if stats['count'] > 0 else 0):.1f}min\u001b[0m\n"
                    f"│ New: \u001b[1;31m+{stats['recent_count']} this week\u001b[0m\n"
                    f"└───────────────\n"
                    f"```"
                )
            else:  # shows
                if name == "TV Shows":
                    emoji = "📺"
                    display_name = "TV SHOWS"
                    color = "36"  # Cyan
                else:  # Anime Shows
                    emoji = "🇯🇵"
                    display_name = "ANIME SHOWS"
                    color = "36;1"  # Bright cyan
                
                lib_stats = (
                    f"```ansi\n"
                    f"\u001b[1;{color}m{emoji} {display_name}\u001b[0m\n\n"
                    f"┌───────────────\n"
                    f"│ Shows: \u001b[1;33m{stats['count']} \u001b[0m"
                    f"\u001b[33mseries\u001b[0m\n"
                    f"│ Episodes: \u001b[1;33m{stats['episodes']} total\u001b[0m\n"
                    f"│ Duration: \u001b[1;36m{stats['duration']}\u001b[0m\n"
                    f"│ Size: \u001b[1;36m{stats['size_gb']:.1f}GB\u001b[0m\n"
                    f"│ Average: \u001b[1;32m{(stats['duration_minutes'] / stats['episodes'] if stats['episodes'] > 0 else 0):.1f}min\u001b[0m\n"
                    f"│ New: \u001b[1;31m+{stats['recent_count']} this week\u001b[0m\n"
                    f"└───────────────\n"
                    f"```"
                )
            
            embed.add_field(name="", value=lib_stats, inline=True)
            
        # Add divider
        embed.add_field(name="", value="───────────────────────", inline=False)
        
        # Sort recent items by date and display top ones with ansi colors
        if recent_items:
            recent_items.sort(key=lambda x: x[3], reverse=True)
            recent_content = "```ansi\n\u001b[1;35mRECENT ADDITIONS\u001b[0m\n"
            
            for i, (title, lib_type, year_or_eps, _) in enumerate(recent_items[:6]):
                if "movie" in lib_type.lower():
                    recent_content += f"• \u001b[1;36m{title}\u001b[0m - {lib_type} ({year_or_eps})\n"
                else:
                    recent_content += f"• \u001b[1;36m{title}\u001b[0m - {lib_type} ({year_or_eps} eps)\n"
            
            recent_content += "```"
            embed.add_field(name="", value=recent_content, inline=False)
        
        # Modern footer with timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /media_stats to refresh"
        )

        # Add Plex logo
        embed.set_thumbnail(url="https://cdn.iconscout.com/icon/free/png-256/plex-3521495-2944935.png")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch media statistics:\n```{str(e)}```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)


class OnboardingView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🎟 Request Access", style=discord.ButtonStyle.primary, custom_id="request_access"))

class ChannelManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="🗑️ Delete Channel", style=discord.ButtonStyle.secondary, custom_id="delete_channel")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user has permission (Admin or Maintainer role)
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(interaction.guild.roles, name="🔧 Maintainer")
        
        if (admin_role and admin_role in interaction.user.roles) or \
           (maintainer_role and maintainer_role in interaction.user.roles):
            has_permission = True
            
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to delete this channel. Only Admins and Maintainers can do this.",
                ephemeral=True
            )
            return
        
        # Delete the channel
        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            await channel.delete()
        except Exception as e:
            await interaction.followup.send(f"❌ Error deleting channel: {str(e)}", ephemeral=True)

class AccessRequestView(View):
    def __init__(self, user_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success, custom_id="approve_request")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user has permission to approve (Admin or Maintainer role)
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(interaction.guild.roles, name="🔧 Maintainer")
        
        if (admin_role and admin_role in interaction.user.roles) or \
           (maintainer_role and maintainer_role in interaction.user.roles):
            has_permission = True
            
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to approve requests. Only Admins and Maintainers can do this.",
                ephemeral=True
            )
            return
            
        try:
            # Get the channel
            channel = interaction.channel
            
            # Try to extract request number from channel name
            request_number = "Unknown"
            try:
                # Channel name format: request-XXXX-username
                channel_name_parts = channel.name.split('-')
                if len(channel_name_parts) >= 2:
                    request_number = channel_name_parts[1]
            except:
                pass
            
            # Acknowledge the interaction first
            await interaction.response.defer()
            
            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
                    return
                    
                # Remove Pending role
                pending_role = discord.utils.get(interaction.guild.roles, name="⏳ Pending")
                if pending_role and pending_role in user.roles:
                    await user.remove_roles(pending_role)
                
                # Remove Denied role if they had it
                denied_role = discord.utils.get(interaction.guild.roles, name="❌ Denied")
                if denied_role and denied_role in user.roles:
                    await user.remove_roles(denied_role)
                
                # Add Approved role
                approved_role = discord.utils.get(interaction.guild.roles, name="🎟️ Approved")
                if approved_role:
                    await user.add_roles(approved_role)
                    
                    # Send approval message in channel with request number
                    embed = discord.Embed(
                        title=f"✅ Request #{request_number} Approved",
                        description=f"{user.mention} has been approved for access!\n\nThey can now access the invite channel.",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed)

                    # Send a DM to the user with request number
                    try:
                        dm_embed = discord.Embed(
                            title=f"🎉 Access Request #{request_number} Approved!",
                            description="Your access request has been approved! You can now access the invite channel.",
                            color=0x00ff00
                        )
                        await user.send(embed=dm_embed)
                    except:
                        # If DM fails, add a note to the channel
                        await channel.send("Note: Could not send DM to user (they may have DMs disabled)")

                    # Add a message about channel deletion
                    await channel.send(
                        f"✅ Request #{request_number} process complete. An admin or maintainer can delete this channel using the button at the top.",
                        delete_after=300  # Delete after 5 minutes
                    )
                else:
                    await interaction.followup.send("❌ Error: Could not find the Approved role.", ephemeral=True)
            except discord.NotFound:
                await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error while approving: {str(e)}", ephemeral=True)

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny_request")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user has permission to deny (Admin or Maintainer role)
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(interaction.guild.roles, name="🔧 Maintainer")
        
        if (admin_role and admin_role in interaction.user.roles) or \
           (maintainer_role and maintainer_role in interaction.user.roles):
            has_permission = True
            
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to deny requests. Only Admins and Maintainers can do this.",
                ephemeral=True
            )
            return
            
        try:
            # Get the channel
            channel = interaction.channel
            
            # Try to extract request number from channel name
            request_number = "Unknown"
            try:
                # Channel name format: request-XXXX-username
                channel_name_parts = channel.name.split('-')
                if len(channel_name_parts) >= 2:
                    request_number = channel_name_parts[1]
            except:
                pass
            
            # Acknowledge the interaction first
            await interaction.response.defer()
            
            try:
                user = await interaction.guild.fetch_member(self.user_id)
                if not user:
                    await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
                    return

                # Remove Pending role
                pending_role = discord.utils.get(interaction.guild.roles, name="⏳ Pending")
                if pending_role and pending_role in user.roles:
                    await user.remove_roles(pending_role)

                # Remove Approved role if they had it
                approved_role = discord.utils.get(interaction.guild.roles, name="🎟️ Approved")
                if approved_role and approved_role in user.roles:
                    await user.remove_roles(approved_role)
                
                # Add Denied role
                denied_role = discord.utils.get(interaction.guild.roles, name="❌ Denied")
                if denied_role:
                    await user.add_roles(denied_role)

                # Send denial message in channel with request number
                embed = discord.Embed(
                    title=f"❌ Request #{request_number} Denied",
                    description=f"{user.mention}'s access request has been denied.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)

                # Send a DM to the user with request number
                try:
                    dm_embed = discord.Embed(
                        title=f"❌ Access Request #{request_number} Denied",
                        description="Your access request has been denied. Please contact a moderator if you have questions.",
                        color=0xff0000
                    )
                    await user.send(embed=dm_embed)
                except:
                    # If DM fails, add a note to the channel
                    await channel.send("Note: Could not send DM to user (they may have DMs disabled)")

                # Add a message about channel deletion
                await channel.send(
                    f"✅ Request #{request_number} process complete. An admin or maintainer can delete this channel using the button at the top.",
                    delete_after=300  # Delete after 5 minutes
                )
            except discord.NotFound:
                await interaction.followup.send("❌ Error: Could not find the user who requested access.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error while denying: {str(e)}", ephemeral=True)

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

def create_onboarding_embed():
    embed = discord.Embed(
        title="🎬 Welcome to Our Media Server!",
        description="",
        color=0x00b8ff
    )

    # English Section
    embed.add_field(
        name="🇬🇧 English",
        value=(
            "**How to Get Started:**\n"
            "1. Click the 'Request Access' button below\n"
            "2. Wait for moderator approval\n"
            "3. Once approved, you'll receive a Plex invite via Wizarr\n"
            "4. Use Overseerr to request new content\n"
            "5. Enjoy your media on Plex!\n\n"
        ),
        inline=False
    )

    # French Section
    embed.add_field(
        name="🇫🇷 Français",
        value=(
            "**Comment commencer:**\n"
            "1. Cliquez sur le bouton 'Demander l'accès' ci-dessous\n"
            "2. Attendez l'approbation d'un modérateur\n"
            "3. Une fois approuvé, vous recevrez une invitation Plex via Wizarr\n"
            "4. Utilisez Overseerr pour demander du nouveau contenu\n"
            "5. Profitez de vos médias sur Plex!\n\n"
        ),
        inline=False
    )

    return embed

@tree.command(
    name="send_intro_embed",
    description="Send the onboarding embed to the start-here channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_intro_embed(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Find the start-here channel
        start_here_channel = discord.utils.get(interaction.guild.channels, name="📖｜start-here")
        if not start_here_channel:
            await interaction.followup.send("❌ Could not find the start-here channel!", ephemeral=True)
            return

        # Create and send the embed
        embed = create_onboarding_embed()
        view = OnboardingView()
        await start_here_channel.send(embed=embed, view=view)
        
        await interaction.followup.send("✅ Onboarding embed sent successfully!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "request_access":
            await handle_access_request(interaction)

# First, create a new view for thread deletion
class ThreadManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="🗑️ Delete Thread", style=discord.ButtonStyle.secondary, custom_id="delete_thread")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the user has permission (Admin or Maintainer role)
        has_permission = False
        admin_role = discord.utils.get(interaction.guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(interaction.guild.roles, name="🔧 Maintainer")
        
        if (admin_role and admin_role in interaction.user.roles) or \
           (maintainer_role and maintainer_role in interaction.user.roles):
            has_permission = True
            
        if not has_permission:
            await interaction.response.send_message(
                "❌ You don't have permission to delete this thread. Only Admins and Maintainers can do this.",
                ephemeral=True
            )
            return
        
        # Delete the thread
        try:
            await interaction.response.defer(ephemeral=True)
            thread = interaction.channel
            await thread.delete()
        except Exception as e:
            await interaction.followup.send(f"❌ Error deleting thread: {str(e)}", ephemeral=True)

# Function to load the request counter
def load_request_counter():
    """Load the request counter from file"""
    try:
        if os.path.exists(COUNTER_STATE_FILE):
            with open(COUNTER_STATE_FILE, "r") as f:
                state = json.load(f)
                return state.get("counter", 0)
    except Exception as e:
        print(f"Error loading request counter: {e}")
    return 0

# Function to save the request counter
def save_request_counter(counter):
    """Save the request counter to a file"""
    try:
        state = {"counter": counter}
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(COUNTER_STATE_FILE), exist_ok=True)
        with open(COUNTER_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error saving request counter: {e}")

# Update the handle_access_request function to use the counter
async def handle_access_request(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        user = interaction.user
        
        # Load and increment the request counter
        request_counter = load_request_counter() + 1
        save_request_counter(request_counter)
        
        # Find the relevant roles
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        pending_role = discord.utils.get(guild.roles, name="⏳ Pending")
        
        # Assign the Pending role to the user
        if pending_role and pending_role not in user.roles:
            try:
                await user.add_roles(pending_role)
            except Exception as e:
                print(f"Error adding Pending role to user: {e}")
        
        # Find the Onboarding category
        onboarding_category = discord.utils.get(guild.categories, name="👋 Onboarding")
        if not onboarding_category:
            await interaction.followup.send("❌ Error: Could not find the Onboarding category!", ephemeral=True)
            return
            
        # Create channel permissions - only the requester, admins, and maintainers can see
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True,
                manage_channels=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True
            )
        }
        
        # Add role permissions
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if maintainer_role:
            overwrites[maintainer_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if bot_role:
            overwrites[bot_role] = discord.PermissionOverwrite(
                read_messages=True, 
                send_messages=True,
                manage_channels=True,
                embed_links=True,
                attach_files=True
            )
        
        # Create a private channel for this request with a numbered name
        channel_name = f"request-{request_counter:04d}-{user.name.lower().replace(' ', '-')}"
        request_channel = await guild.create_text_channel(
            name=channel_name,
            category=onboarding_category,
            overwrites=overwrites,
            topic=f"Access request #{request_counter} from {user.name} ({user.id})"
        )
        
        # Send a management message for admins/mods with delete button
        admin_embed = discord.Embed(
            title=f"🔧 Request Management #{request_counter}",
            description=f"This is a private channel for an access request from {user.mention}.\n\n" +
                       f"{admin_role.mention if admin_role else 'Admins'} and " +
                       f"{maintainer_role.mention if maintainer_role else 'Maintainers'}: " +
                       f"You can delete this channel using the button below when finished.",
            color=0x808080  # Gray
        )
        
        # Send admin message with delete button
        channel_mgmt_view = ChannelManagementView()
        await request_channel.send(embed=admin_embed, view=channel_mgmt_view)
        
        # Then send the user request embed
        user_embed = discord.Embed(
            title=f"🎟 Access Request #{request_counter}",
            description=f"User: {user.mention}\n\nPlease explain why you want access to the media server:",
            color=0x00b8ff
        )
        
        # Add a note indicating they've been assigned the Pending role
        if pending_role:
            user_embed.add_field(
                name="Status",
                value=f"You've been assigned the {pending_role.mention} role while your request is processed.",
                inline=False
            )
        
        # Create access request view with user ID
        request_view = AccessRequestView(user.id, request_channel.id)
        await request_channel.send(embed=user_embed, view=request_view)
        
        # Notify the user with a link to the private channel
        await interaction.followup.send(
            f"✅ Your access request #{request_counter} has been submitted! Please check the private channel: {request_channel.mention}",
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error: {str(e)}",
            ephemeral=True
        )

def create_invite_embed():
    embed = discord.Embed(
        title="🎟️ Get Your Media Server Invite",
        description=(
            "Welcome to the invite channel! Here's your direct invite link:\n\n"
            "**🔗 [Click Here to Join](https://wizarr.tessdev.fr/i/ETHUDN)**\n\n"
            "Follow the steps below to get started with our media server."
        ),
        color=0x00b8ff
    )

    # English Section
    embed.add_field(
        name="🇬🇧 Getting Started",
        value=(
            "**Step 1: Get Your Plex Invite**\n"
            "• Click the invite link above\n"
            "• Sign up with your email\n"
            "• Accept the Plex invitation\n\n"
            "**Step 2: Access Content**\n"
            "• Download [Plex](https://www.plex.tv/downloads)\n"
            "• Sign in with your account\n"
            "• Start streaming!\n\n"
            "**Step 3: Request Content**\n"
            "• Use [Overseerr](https://overseer.tessdev.fr) to request movies and shows\n"
            "• Track your requests status\n"
            "• Get notified when content is available"
        ),
        inline=False
    )

    # French Section
    embed.add_field(
        name="🇫🇷 Pour Commencer",
        value=(
            "**Étape 1: Obtenir Votre Invitation Plex**\n"
            "• Cliquez sur le lien d'invitation ci-dessus\n"
            "• Inscrivez-vous avec votre email\n"
            "• Acceptez l'invitation Plex\n\n"
            "**Étape 2: Accéder au Contenu**\n"
            "• Téléchargez [Plex](https://www.plex.tv/downloads)\n"
            "• Connectez-vous avec votre compte\n"
            "• Commencez à streamer!\n\n"
            "**Étape 3: Demander du Contenu**\n"
            "• Utilisez [Overseerr](https://overseer.tessdev.fr) pour demander des films et séries\n"
            "• Suivez le statut de vos demandes\n"
            "• Soyez notifié quand le contenu est disponible"
        ),
        inline=False
    )

    # Important Notes
    embed.add_field(
        name="ℹ️ Important Notes | Notes Importantes",
        value=(
            "**🇬🇧**\n"
            "• This invite link is for approved members only\n"
            "• Keep your login information secure\n"
            "• Don't share your account with others\n"
            "• For support, contact an admin\n\n"
            "**🇫🇷**\n"
            "• Ce lien d'invitation est réservé aux membres approuvés\n"
            "• Gardez vos informations de connexion sécurisées\n"
            "• Ne partagez pas votre compte\n"
            "• Pour le support, contactez un admin"
        ),
        inline=False
    )

    embed.set_footer(
        text="🔐 Access is limited to approved members only | Accès limité aux membres approuvés",
        icon_url="https://cdn.discordapp.com/emojis/1039485258276737024.webp?size=96&quality=lossless"
    )

    return embed

@tree.command(
    name="send_invite_embed",
    description="Send the get-invite embed to the channel.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_invite_embed(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Find the get-invite channel
        invite_channel = discord.utils.get(interaction.guild.channels, name="📬｜get-invite")
        if not invite_channel:
            await interaction.followup.send("❌ Could not find the get-invite channel!", ephemeral=True)
            return

        # Create and send the embed
        embed = create_invite_embed()
        await invite_channel.send(embed=embed)
        
        await interaction.followup.send("✅ Invite embed sent successfully!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@tree.command(
    name="fix_permissions",
    description="Fix permissions for all roles and channels",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_permissions(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        results = []
        
        # Get all roles
        everyone_role = guild.default_role
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")
        
        # Define expected role permissions
        expected_permissions = {
            "🛡️ Admin": discord.Permissions(administrator=True),
            "👀 Observer": discord.Permissions(
                view_channel=True,
                read_messages=True,
                read_message_history=True
            ),
            "🔧 Maintainer": discord.Permissions(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                kick_members=True,
                manage_channels=True,
                create_public_threads=True,
                create_private_threads=True,
                manage_threads=True,
                moderate_members=True
            ),
            "🤖 Bot": discord.Permissions(
                view_channel=True,
                send_messages=True,
                send_messages_in_threads=True,
                create_public_threads=True,
                create_private_threads=True,
                manage_threads=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                mention_everyone=True,
                use_external_emojis=True,
                add_reactions=True,
                manage_roles=True,
                manage_channels=True,
                manage_messages=True,
                moderate_members=True
            ),
            "🎮 Gamer": discord.Permissions(read_messages=True),
            "🎟️ Approved": discord.Permissions(read_messages=True),
            "⏳ Pending": discord.Permissions(read_messages=True),
            "❌ Denied": discord.Permissions(read_messages=True)
        }
        
        # Check and fix roles
        for role_name, expected_perms in expected_permissions.items():
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                results.append(f"❌ Role not found: {role_name}")
                continue
                
            # Compare permissions
            if role.permissions != expected_perms:
                try:
                    await role.edit(permissions=expected_perms)
                    results.append(f"✅ Fixed permissions for role: {role_name}")
                except discord.Forbidden:
                    results.append(f"❌ Cannot edit permissions for role: {role_name} (Forbidden)")
                except Exception as e:
                    results.append(f"❌ Error fixing role {role_name}: {str(e)}")
            else:
                results.append(f"✓ Role permissions are correct: {role_name}")
        
        # Reset @everyone permissions
        try:
            await everyone_role.edit(permissions=discord.Permissions(
                view_channel=False,  # This is key - default can't view channels
                connect=True,
                speak=False,
                use_application_commands=True,
                use_embedded_activities=True
            ))
            results.append("✅ Set @everyone to hide all channels by default")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone permissions: {str(e)}")
        
        # Process ALL categories that exist
        for category in guild.categories:
            try:
                # Create category overwrites
                overwrites = {
                    everyone_role: discord.PermissionOverwrite(view_channel=False, read_messages=False)
                }
                
                # Add admin/maintainer permissions
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        send_messages=True
                    )
                
                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        send_messages=True
                    )
                
                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
                
                # Only give approved users access to non-admin categories
                is_admin_category = (
                    "admin" in category.name.lower() or 
                    "alert" in category.name.lower() or
                    "bot command" in category.name.lower()
                )
                
                # If it's a normal category, allow approved users access
                if approved_role and not is_admin_category and "onboarding" not in category.name.lower():
                    overwrites[approved_role] = discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        send_messages=True
                    )
                
                # Apply the overwrites to the category
                await category.edit(overwrites=overwrites)
                results.append(f"✅ Set default permissions for category: {category.name}")
                
                # Sync all channels in the category (except special ones)
                for channel in category.channels:
                    # Skip special channels
                    if channel.name == "📖｜start-here" or channel.name == "📬｜get-invite" or channel.name == "🎫｜access-requests" or channel.name.startswith("🔒"):
                        continue
                    
                    try:
                        await channel.edit(sync_permissions=True)
                        results.append(f"✅ Synced permissions for: {channel.name}")
                    except Exception as e:
                        results.append(f"❌ Failed to sync {channel.name}: {str(e)}")
            except Exception as e:
                results.append(f"❌ Error setting category {category.name}: {str(e)}")
        
        # Special channel permissions
        special_channels = {
            "📖｜start-here": {
                "default": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True, 
                    read_message_history=True,  # Ensure message history is readable
                    send_messages=False
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True
                )
            },
            "📬｜get-invite": {
                "default": discord.PermissionOverwrite(view_channel=False, read_messages=False),
                "🎟️ Approved": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,  # Ensure message history is readable
                    send_messages=False
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True
                )
            },
            "🎫｜access-requests": {
                "default": discord.PermissionOverwrite(view_channel=False, read_messages=False),
                "🛡️ Admin": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True
                ),
                "🔧 Maintainer": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True
                ),
                "🤖 Bot": discord.PermissionOverwrite(
                    view_channel=True, 
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True
                )
            }
        }
        
        # Add any channels with "admin" in name or starting with 🔒
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
                
            if "admin" in channel.name.lower() or channel.name.startswith("🔒"):
                special_channels[channel.name] = {
                    "default": discord.PermissionOverwrite(view_channel=False, read_messages=False),
                    "🛡️ Admin": discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True
                    ),
                    "🔧 Maintainer": discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True
                    ),
                    "🤖 Bot": discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True
                    )
                }
        
        # Apply special channel permissions
        for channel_name, perms in special_channels.items():
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                # Try to find by partial match if exact match fails
                for guild_channel in guild.channels:
                    if channel_name in guild_channel.name:
                        channel = guild_channel
                        break
            
            if not channel:
                results.append(f"❌ Channel not found: {channel_name}")
                continue
                
            # Set channel permissions
            for role_name, overwrite in perms.items():
                if role_name == "default":
                    try:
                        await channel.set_permissions(everyone_role, overwrite=overwrite)
                        results.append(f"✅ Set default permissions for channel: {channel.name}")
                    except Exception as e:
                        results.append(f"❌ Error setting default permissions for channel {channel.name}: {str(e)}")
                else:
                    role = discord.utils.get(guild.roles, name=role_name)
                    if not role:
                        results.append(f"❌ Role not found for channel permission: {role_name}")
                        continue
                        
                    try:
                        await channel.set_permissions(role, overwrite=overwrite)
                        results.append(f"✅ Set {role_name} permissions for channel: {channel.name}")
                    except Exception as e:
                        results.append(f"❌ Error setting {role_name} permissions for channel {channel.name}: {str(e)}")
        
        # Fix request channels for users
        request_channels = [ch for ch in guild.channels if ch.name.startswith("request-")]
        for channel in request_channels:
            try:
                # Extract the username from the channel name (format is request-XXXX-username)
                channel_parts = channel.name.split('-')
                if len(channel_parts) >= 3:
                    # Get everything after the second dash
                    username = '-'.join(channel_parts[2:])
                    
                    # Try to find the user with this name
                    target_user = None
                    for member in guild.members:
                        if member.name.lower() == username.lower() or username.lower() in member.name.lower():
                            target_user = member
                            break
                    
                    if target_user:
                        # Update the user's permissions to read history
                        await channel.set_permissions(
                            target_user,
                            view_channel=True,
                            read_messages=True,
                            read_message_history=True,
                            send_messages=True
                        )
                        results.append(f"✅ Fixed permissions for {channel.name} - {target_user.name} can now read history")
                    else:
                        results.append(f"❌ Could not find user for channel: {channel.name}")
            except Exception as e:
                results.append(f"❌ Error fixing {channel.name}: {str(e)}")
                
        # Create an embed with the results
        embed = discord.Embed(
            title="🔧 Permission Check Results",
            description="Here's what was fixed:",
            color=0x00b8ff
        )
        
        # Split results into chunks to avoid hitting embed field limits
        chunks = [results[i:i+10] for i in range(0, len(results), 10)]
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Results {i+1}/{len(chunks)}",
                value="\n".join(chunk),
                inline=False
            )
        
        # Add summary
        embed.add_field(
            name="Summary",
            value=(
                "✅ Permission structure:\n"
                "• New users can only see the start-here channel\n"
                "• Start-here history is visible to everyone\n"
                "• All request channels allow users to see their history\n"
                "• Admin channels are restricted to admins and maintainers\n"
                "• Approved users can't access admin areas\n"
                "• Approved users can access media channels"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error updating permissions: {str(e)}", ephemeral=True)

# Add this to handle command errors globally
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        # Handle missing permissions gracefully
        await interaction.response.send_message(
            "❌ You don't have permission to use this command. This command requires administrator privileges.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.CommandOnCooldown):
        # Handle cooldown errors
        await interaction.response.send_message(
            f"⏳ This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.errors.CommandNotFound):
        # Handle command not found errors
        await interaction.response.send_message(
            "❓ Command not found. Use `/commands` to see available commands.",
            ephemeral=True
        )
    else:
        # Handle any other errors
        await interaction.response.send_message(
            f"❌ An error occurred: {str(error)}",
            ephemeral=True
        )
        # Log the full error to console
        print(f"Command error: {error}")

@tree.command(
    name="restrict_channels",
    description="Strictly restrict channel visibility for new users",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def restrict_channels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        results = []
        
        # Find all roles
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")
        
        # Make sure @everyone has minimal base permissions
        everyone_role = guild.default_role
        try:
            # Reset the base @everyone permissions to bare minimum
            base_perms = discord.Permissions(
                # These are the bare minimum permissions
                view_channel=False,  # Can't view any channels by default
                connect=False,  # Can't connect to voice channels
                use_application_commands=True,  # Can use slash commands
                use_embedded_activities=True,  # Can use activities
                create_instant_invite=False,  # Can't create invites
            )
            await everyone_role.edit(permissions=base_perms)
            results.append("✅ Reset @everyone role to minimal permissions")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone permissions: {str(e)}")
        
        # Find the start-here channel - the only one visible to everyone
        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        
        # Go through EVERY channel in the server
        for channel in guild.channels:
            # Skip categories for now
            if isinstance(channel, discord.CategoryChannel):
                continue
                
            try:
                # Default: DENY access to everyone except in start-here
                if channel == start_here:
                    # For start-here: everyone can see, only bot/admins can send
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=True,
                            read_messages=True,
                            send_messages=False
                        )
                    }
                    results.append(f"✅ Set start-here channel visible to everyone")
                elif channel.name == "📬｜get-invite":
                    # Only approved users can see this
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False,
                            read_messages=False
                        )
                    }
                    if approved_role:
                        overwrites[approved_role] = discord.PermissionOverwrite(
                            view_channel=True,
                            read_messages=True,
                            send_messages=False
                        )
                    results.append(f"✅ Set get-invite channel for approved users only")
                elif channel.name.startswith("🔒") or channel.name.startswith("🎫"):
                    # Admin/maintainer only channels
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False,
                            read_messages=False
                        )
                    }
                    results.append(f"✅ Set {channel.name} to admin/maintainer only")
                else:
                    # All other channels: visible only to approved users
                    overwrites = {
                        everyone_role: discord.PermissionOverwrite(
                            view_channel=False,
                            read_messages=False
                        )
                    }
                    if approved_role:
                        overwrites[approved_role] = discord.PermissionOverwrite(
                            view_channel=True,
                            read_messages=True
                        )
                    results.append(f"✅ Set {channel.name} to approved users only")
                
                # Always add admin, maintainer and bot permissions
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
                
                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True
                    )
                
                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True
                    )
                
                # Apply the permission overwrites to the channel
                await channel.edit(overwrites=overwrites)
                
            except Exception as e:
                results.append(f"❌ Error setting permissions for {channel.name}: {str(e)}")
        
        # Create an embed with the results
        embed = discord.Embed(
            title="🔒 Channel Restriction Results",
            description="**STRICT PERMISSIONS APPLIED**",
            color=0xFF0000
        )
        
        # Split results into chunks to avoid hitting embed field limits
        chunks = [results[i:i+15] for i in range(0, len(results), 15)]
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Results {i+1}/{len(chunks)}",
                value="\n".join(chunk),
                inline=False
            )
        
        # Add final summary
        embed.add_field(
            name="⚠️ IMPORTANT",
            value=(
                "**These changes are strict and may restrict access more than expected:**\n"
                "• New users can ONLY see the start-here channel\n"
                "• ALL other channels are hidden until approved\n"
                "• @everyone permissions have been reset to minimal\n"
                "• Channel-specific permissions override category permissions\n\n"
                "If any channel is still visible to unapproved users, please report it."
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error restricting channels: {str(e)}", ephemeral=True)

def start_bot():
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN is not set")
        return
    if not TEST_GUILD_ID:
        print("❌ Error: TEST_GUILD_ID is not set")
        return
    bot.run(TOKEN)

@tree.command(
    name="lock_server",
    description="EMERGENCY: Lock down all channels for new users",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def lock_server(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        results = []
        fixed_channels = 0
        
        # Get all roles
        everyone_role = guild.default_role
        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
        maintainer_role = discord.utils.get(guild.roles, name="🔧 Maintainer")
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        approved_role = discord.utils.get(guild.roles, name="🎟️ Approved")
        
        # Forcefully reset @everyone permissions to absolute minimum
        try:
            minimal_perms = discord.Permissions(
                # Absolute minimum permissions
                connect=False,
                speak=False,
                send_messages=False,
                read_messages=False,
                view_channel=False,
                # Keep basic functionality
                use_application_commands=True,
                use_embedded_activities=True
            )
            await everyone_role.edit(permissions=minimal_perms)
            results.append("✅ Reset @everyone permissions to absolute minimum")
        except Exception as e:
            results.append(f"❌ Failed to reset @everyone: {str(e)}")
        
        # Find start-here channel - the ONLY one that should be visible
        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        
        # Step 1: Reset all categories first with explicit denies
        for category in guild.categories:
            try:
                overwrites = {
                    # Explicit deny for everyone
                    everyone_role: discord.PermissionOverwrite(
                        view_channel=False,
                        read_messages=False,
                        send_messages=False,
                        read_message_history=False,
                        connect=False,
                        speak=False
                    )
                }
                
                # Add role permissions
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True
                    )
                
                if maintainer_role:
                    overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True
                    )
                
                if bot_role:
                    overwrites[bot_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True
                    )
                
                if approved_role and category.name != "👋 Onboarding":
                    # Only give approved users access to non-onboarding categories
                    overwrites[approved_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True
                    )
                
                await category.edit(overwrites=overwrites)
                results.append(f"✅ Set strict permissions for category: {category.name}")
                
                # Force sync all channels in this category to match category permissions
                for channel in category.channels:
                    try:
                        # Skip the start-here channel - we'll handle it separately
                        if channel == start_here:
                            continue
                            
                        # Admin-only channels should stay admin-only
                        if channel.name.startswith("🔒") or channel.name.startswith("🎫") or channel.name == "📬｜get-invite" or "admin" in channel.name:
                            # Create special permissions for admin/invite channels
                            special_overwrites = {
                                everyone_role: discord.PermissionOverwrite(
                                    view_channel=False,
                                    read_messages=False,
                                    send_messages=False
                                )
                            }
                            
                            if admin_role:
                                special_overwrites[admin_role] = discord.PermissionOverwrite(
                                    view_channel=True,
                                    read_messages=True,
                                    send_messages=True
                                )
                                
                            if maintainer_role:
                                special_overwrites[maintainer_role] = discord.PermissionOverwrite(
                                    view_channel=True,
                                    read_messages=True,
                                    send_messages=True
                                )
                                
                            if bot_role:
                                special_overwrites[bot_role] = discord.PermissionOverwrite(
                                    view_channel=True,
                                    read_messages=True,
                                    send_messages=True
                                )
                                
                            # For get-invite channel, also allow approved users
                            if channel.name == "📬｜get-invite" and approved_role:
                                special_overwrites[approved_role] = discord.PermissionOverwrite(
                                    view_channel=True,
                                    read_messages=True,
                                    send_messages=False
                                )
                                
                            await channel.edit(overwrites=special_overwrites, sync_permissions=False)
                            results.append(f"✅ Set restricted permissions for {channel.name}")
                        else:
                            # For normal channels, sync with category
                            await channel.edit(sync_permissions=True)
                            results.append(f"✅ Synced {channel.name} with category permissions")
                        
                        fixed_channels += 1
                    except Exception as e:
                        results.append(f"❌ Failed to set {channel.name}: {str(e)}")
                
            except Exception as e:
                results.append(f"❌ Failed to set category {category.name}: {str(e)}")
        
        # Handle start-here channel separately with explicit permissions
        if start_here:
            try:
                start_here_overwrites = {
                    everyone_role: discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=False,
                        read_message_history=True
                    ),
                    bot_role: discord.PermissionOverwrite(
                        view_channel=True, 
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True
                    )
                }
                
                if admin_role:
                    start_here_overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True
                    )
                
                if maintainer_role:
                    start_here_overwrites[maintainer_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        send_messages=True,
                        read_message_history=True
                    )
                
                await start_here.edit(overwrites=start_here_overwrites, sync_permissions=False)
                results.append(f"✅ Set start-here visible to everyone but read-only")
                fixed_channels += 1
            except Exception as e:
                results.append(f"❌ Failed to set start-here channel: {str(e)}")
        
        # Create an embed with the results
        embed = discord.Embed(
            title="🚨 EMERGENCY SERVER LOCKDOWN",
            description="**The server has been locked down with strict permissions:**",
            color=0xFF0000
        )
        
        # Add stats
        embed.add_field(
            name="📊 Stats",
            value=f"• Fixed {fixed_channels} channels\n• Reset @everyone permissions\n• Applied explicit denies everywhere",
            inline=False
        )
        
        # Split results into chunks
        chunks = [results[i:i+10] for i in range(0, len(results), 10)]
        for i, chunk in enumerate(chunks[:3]):  # Limit to first 3 chunks to avoid too many fields
            embed.add_field(
                name=f"Results {i+1}/{min(len(chunks), 3)}",
                value="\n".join(chunk),
                inline=False
            )
        
        # Add security notes
        embed.add_field(
            name="🔐 Security Configuration",
            value=(
                "**STRICT ACCESS CONTROL ENABLED:**\n"
                "• New users can ONLY see start-here channel\n"
                "• All other channels are completely hidden\n"
                "• Category permissions reset with explicit denies\n"
                "• Channel-specific permissions applied\n"
                "• @everyone role has been locked down"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Emergency lockdown failed: {str(e)}", ephemeral=True)

@tree.command(
    name="fix_start_here",
    description="Fix start-here channel permissions",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_start_here(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        everyone_role = guild.default_role
        bot_role = discord.utils.get(guild.roles, name="🤖 Bot")
        
        # Find start-here channel
        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        if not start_here:
            # Try partial match
            for channel in guild.channels:
                if "start-here" in channel.name:
                    start_here = channel
                    break
        
        if not start_here:
            await interaction.followup.send("❌ Could not find the start-here channel!", ephemeral=True)
            return
            
        # Set explicit permissions for everyone to see and read but not write
        await start_here.set_permissions(
            everyone_role, 
            view_channel=True,
            read_messages=True,
            read_message_history=True,
            send_messages=False
        )
        
        # Make sure bot can send messages
        if bot_role:
            await start_here.set_permissions(
                bot_role,
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True
            )
            
        await interaction.followup.send("✅ Fixed start-here channel! Everyone can now view messages but not send them.", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@tree.command(
    name="fix_read_permissions",
    description="Fix read history permissions for important channels",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def fix_read_permissions(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        everyone_role = guild.default_role
        results = []
        
        # 1. Fix start-here channel
        start_here = discord.utils.get(guild.channels, name="📖｜start-here")
        if start_here:
            # Everyone should be able to view channel and read history
            await start_here.set_permissions(
                everyone_role, 
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False
            )
            results.append("✅ Fixed start-here channel - everyone can now read message history")
        else:
            results.append("❌ Could not find start-here channel")
        
        # 2. Fix all request channels - ensure users can read history in their own request channel
        request_channels = [channel for channel in guild.channels if channel.name.startswith("request-")]
        for channel in request_channels:
            try:
                # Extract the username from the channel name (format is request-XXXX-username)
                channel_parts = channel.name.split('-')
                if len(channel_parts) >= 3:
                    # Get everything after the second dash
                    username = '-'.join(channel_parts[2:])
                    
                    # Try to find the user with this name
                    target_user = None
                    for member in guild.members:
                        if member.name.lower() == username.lower() or username.lower() in member.name.lower():
                            target_user = member
                            break
                    
                    if target_user:
                        # Update the user's permissions to read history
                        await channel.set_permissions(
                            target_user,
                            view_channel=True,
                            read_messages=True,
                            read_message_history=True,
                            send_messages=True
                        )
                        results.append(f"✅ Fixed permissions for {channel.name} - {target_user.name} can now read history")
                    else:
                        results.append(f"❌ Could not find user for channel: {channel.name}")
            except Exception as e:
                results.append(f"❌ Error fixing {channel.name}: {str(e)}")
                
        embed = discord.Embed(
            title="🔧 Read Permission Fix",
            description="Results of fixing read permissions:",
            color=0x00b8ff
        )
        
        embed.add_field(name="Changes", value="\n".join(results), inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


if __name__ == "__main__":
    start_bot()
