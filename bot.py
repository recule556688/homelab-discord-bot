import os
import time
import psutil
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load settings from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Set your test guild ID here (as an integer). This is for instant slash command sync while testing.
# You can also define it in your .env file and fetch it via os.getenv("TEST_GUILD_ID")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID"))

# Set up the bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Global variables to store the dashboard embed message and the channel it's in.
dashboard_message = None
dashboard_channel = None


def create_health_embed():
    # Calculate uptime (since system boot) formatted as h m s.
    uptime_seconds = time.time() - psutil.boot_time()
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    # Gather CPU and RAM usage using psutil
    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    # Build the embed
    embed = discord.Embed(title="🖥️ Server Health Dashboard", color=0x00FF00)
    embed.add_field(name="Uptime", value=uptime_str, inline=False)
    embed.add_field(name="CPU Usage", value=f"{cpu_usage}%", inline=True)
    embed.add_field(name="RAM Usage", value=f"{memory.percent}%", inline=True)
    embed.set_footer(text="Updated every 30 seconds")
    return embed


@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")
    try:
        # Sync commands to the test guild for instant availability.
        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {TEST_GUILD_ID}")
    except Exception as e:
        print(f"❌ Sync failed: {e}")


@tree.command(
    name="dashboard",
    description="Start a persistent server health dashboard.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def dashboard(interaction: discord.Interaction):
    global dashboard_message, dashboard_channel
    dashboard_channel = interaction.channel

    # Send an ephemeral message so the user knows the dashboard is starting.
    await interaction.response.send_message(
        "Starting dashboard... (This message is ephemeral)", ephemeral=True
    )

    # Post the first dashboard embed publicly
    embed = create_health_embed()
    dashboard_message = await dashboard_channel.send(embed=embed)

    # Start the background update loop if it isn't running already.
    if not update_dashboard.is_running():
        update_dashboard.start()


@tasks.loop(seconds=30)
async def update_dashboard():
    global dashboard_message
    if dashboard_message:
        try:
            new_embed = create_health_embed()
            await dashboard_message.edit(embed=new_embed)
        except Exception as e:
            print(f"Error updating dashboard: {e}")


@tree.command(
    name="serverhealth",
    description="Check current server health stats.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def server_health(interaction: discord.Interaction):
    uptime_seconds = time.time() - psutil.boot_time()
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

    cpu_usage = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    message = (
        f"**Server Health:**\n"
        f"**Uptime:** {uptime_str}\n"
        f"**CPU Usage:** {cpu_usage}%\n"
        f"**RAM Usage:** {memory.percent}%\n"
    )
    await interaction.response.send_message(message, ephemeral=True)


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

    roles = {
        "🛡️ Admin": discord.Permissions(administrator=True),
        "👀 Observer": discord.Permissions(view_channel=True),
        "🔧 Maintainer": discord.Permissions(manage_messages=True),
        "🤖 Bot": discord.Permissions(send_messages=True),
        "🎮 Gamer": discord.Permissions(read_messages=True),
    }

    # Create roles
    for name, perms in roles.items():
        await guild.create_role(name=name, permissions=perms)

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
    }

    # Create each category and its channels.
    for category_name, channels in categories.items():
        category = await guild.create_category(category_name)
        for ch in channels:
            await guild.create_text_channel(ch, category=category)

    await interaction.followup.send("🎉 Server structure created successfully!")


def start_bot():
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN is not set")
        return
    if not TEST_GUILD_ID:
        print("❌ Error: TEST_GUILD_ID is not set")
        return
    bot.run(TOKEN)


if __name__ == "__main__":
    start_bot()
