"""Server setup extension - setup_homelab and sync commands."""

import discord
from discord import app_commands

from ..bot import tree
from ..config import TEST_GUILD_ID


@tree.command(
    name="setup_homelab",
    description="Set up the homelab server layout with roles and channels.",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def setup_homelab(interaction: discord.Interaction):
    """Set up server structure with roles and channels."""
    await interaction.response.defer()
    guild = interaction.guild

    roles = {
        "🛡️ Admin": discord.Permissions(administrator=True),
        "👀 Observer": discord.Permissions(view_channel=True),
        "🔧 Maintainer": discord.Permissions(manage_messages=True),
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
            moderate_members=True,
        ),
        "🎮 Gamer": discord.Permissions(read_messages=True),
        "🎟️ Approved": discord.Permissions(read_messages=True),
        "⏳ Pending": discord.Permissions(read_messages=True),
        "❌ Denied": discord.Permissions(read_messages=True),
    }

    for name, perms in roles.items():
        existing_role = discord.utils.get(guild.roles, name=name)
        if not existing_role:
            await guild.create_role(name=name, permissions=perms)
            print(f"Created role: {name}")

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
        "👋 Onboarding": [
            "📖｜start-here",
            "📬｜get-invite",
            "🎫｜access-requests",
        ],
    }

    for category_name, channels in categories.items():
        existing_category = discord.utils.get(guild.categories, name=category_name)
        if not existing_category:
            category = await guild.create_category(category_name)
            print(f"Created category: {category_name}")
        else:
            category = existing_category
            print(f"Using existing category: {category_name}")

        for channel_name in channels:
            existing_channel = discord.utils.get(guild.channels, name=channel_name)
            if not existing_channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        create_public_threads=True,
                        create_private_threads=True,
                        send_messages_in_threads=True,
                        manage_threads=True,
                        manage_messages=True,
                        embed_links=True,
                        attach_files=True,
                        add_reactions=True,
                        manage_roles=True,
                    ),
                }

                if category_name == "👋 Onboarding":
                    if channel_name == "📖｜start-here":
                        overwrites[guild.default_role] = discord.PermissionOverwrite(
                            read_messages=True
                        )
                    elif channel_name == "📬｜get-invite":
                        approved_role = discord.utils.get(
                            guild.roles, name="🎟️ Approved"
                        )
                        if approved_role:
                            overwrites[approved_role] = discord.PermissionOverwrite(
                                read_messages=True
                            )
                    elif channel_name == "🎫｜access-requests":
                        admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
                        maintainer_role = discord.utils.get(
                            guild.roles, name="🔧 Maintainer"
                        )
                        if admin_role:
                            overwrites[admin_role] = discord.PermissionOverwrite(
                                read_messages=True
                            )
                        if maintainer_role:
                            overwrites[maintainer_role] = discord.PermissionOverwrite(
                                read_messages=True
                            )

                await guild.create_text_channel(
                    channel_name, category=category, overwrites=overwrites
                )
                print(f"Created channel: {channel_name}")

    await interaction.followup.send("🎉 Server structure created/updated successfully!")


@tree.command(
    name="sync",
    description="Sync slash commands (Admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    """Manually sync slash commands."""
    await interaction.response.defer(ephemeral=True)
    try:
        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        await interaction.followup.send(
            f"✅ Successfully synced {len(synced)} commands to guild {TEST_GUILD_ID}",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to sync commands: {e}", ephemeral=True
        )
