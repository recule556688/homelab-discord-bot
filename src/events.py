"""Event handlers for the Discord bot."""

import os
import re

import discord
from discord import app_commands

from .bot import bot, tree
from .config import DASHBOARD_STATE_FILE, NEWBIE_ROLE_ID, TEST_GUILD_ID
from .extensions.dashboard import set_dashboard_state, update_dashboard
from .extensions.overseerr import cache_overseerr_users, get_discord_id_for_overseerr_user
from .extensions.onboarding import handle_access_request
from .extensions.media_votes import (
    auto_create_votes,
    handle_vote_interaction,
    resolve_expired_votes,
)
from .utils import load_dashboard_state


@bot.event
async def on_ready():
    """Handle bot ready event - sync commands and restore dashboard."""
    print(f"🤖 Logged in as {bot.user}")
    try:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="You and all your hardware 😏"
            ),
        )

        guild = discord.Object(id=TEST_GUILD_ID)
        synced = await tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} commands to guild {TEST_GUILD_ID}")

        # Restore dashboard if it exists
        state = load_dashboard_state()
        if state:
            try:
                channel = await bot.fetch_channel(state["channel_id"])
                message = await channel.fetch_message(state["message_id"])
                set_dashboard_state(message, channel)
                if not update_dashboard.is_running():
                    update_dashboard.start()
                print("✅ Restored dashboard state")
            except discord.NotFound:
                print("❌ Could not restore dashboard - message or channel not found")
                if os.path.exists(DASHBOARD_STATE_FILE):
                    os.remove(DASHBOARD_STATE_FILE)

        # Start Overseerr user cache task
        if not cache_overseerr_users.is_running():
            cache_overseerr_users.start()

        # Start media vote tasks
        if not resolve_expired_votes.is_running():
            resolve_expired_votes.start()
        if not auto_create_votes.is_running():
            auto_create_votes.start()
    except Exception as e:
        print(f"❌ Sync failed: {e}")


@bot.event
async def on_member_join(member):
    """Assign Newbie role to new members."""
    try:
        newbie_role = member.guild.get_role(NEWBIE_ROLE_ID)

        if newbie_role:
            await member.add_roles(newbie_role)
            print(f"✅ Added Newbie role to {member.name}")

            welcome_channel = discord.utils.get(
                member.guild.channels, name="📖｜start-here"
            )
            if welcome_channel:
                await welcome_channel.send(
                    f"Welcome {member.mention}! You've been assigned the {newbie_role.name} role."
                )
        else:
            print(f"❌ Could not find Newbie role with ID {NEWBIE_ROLE_ID}")

    except Exception as e:
        print(f"❌ Error assigning Newbie role to {member.name}: {e}")


@bot.event
async def on_message(message):
    """Handle messages - process Overseerr webhook notifications."""
    if message.author == bot.user:
        return

    if message.webhook_id and message.embeds:
        try:
            embed = message.embeds[0]

            is_available_notification = False

            if "Available" in embed.title:
                is_available_notification = True

            if not is_available_notification:
                for field in embed.fields:
                    if field.name == "Request Status" and field.value == "Available":
                        is_available_notification = True
                        break

            if is_available_notification:
                media_title = None
                if embed.title == "Movie Request Now Available":
                    if hasattr(embed, "description") and embed.description:
                        first_line = (
                            embed.description.split("\n")[0]
                            if "\n" in embed.description
                            else embed.description
                        )
                        media_title = first_line
                else:
                    media_title = embed.title

                requester = None

                for field in embed.fields:
                    if field.name == "Requested By":
                        requester = field.value
                        break

                if (
                    not requester
                    and hasattr(embed, "description")
                    and embed.description
                ):
                    requester_match = re.search(
                        r"Requested By\s*\n([^\n]+)", embed.description
                    )
                    if requester_match:
                        requester = requester_match.group(1).strip()

                if not requester and hasattr(embed, "footer") and embed.footer.text:
                    requester_match = re.search(
                        r"Requested By[:\s]+([^\n]+)", embed.footer.text
                    )
                    if requester_match:
                        requester = requester_match.group(1).strip()

                if requester:
                    cleaned_requester = re.sub(r"[<>@*_~|`]", "", requester).strip()

                    discord_id = get_discord_id_for_overseerr_user(cleaned_requester)

                    if discord_id:
                        guild = message.guild
                        try:
                            member = await guild.fetch_member(int(discord_id))
                            if member:
                                notification_channel = None
                                for channel in guild.channels:
                                    if channel.name == "🍿｜now-available":
                                        notification_channel = channel
                                        break

                                if notification_channel is None:
                                    notification_channel = message.channel
                                    print(
                                        "Warning: Notification channel '🍿｜now-available' not found, using original channel"
                                    )

                                notification = (
                                    f"🎉 Hey {member.mention}! **{media_title}** that you requested is now available on Plex!\n"
                                    f"🎉 Salut {member.mention}! **{media_title}** que tu as demandé est maintenant disponible sur Plex!\n\n"
                                    f"🎬 Enjoy watching!\n"
                                    f"🎬 Bon visionnage!"
                                )
                                await notification_channel.send(notification)
                            else:
                                print(f"Member not found for discord_id: {discord_id}")
                        except Exception as e:
                            print(f"Error notifying user: {e}")
                    else:
                        print(
                            f"No Discord ID found for Overseerr user: '{cleaned_requester}'"
                        )
                else:
                    print("Could not extract requester from embed")
        except Exception as e:
            print(f"Error processing webhook: {e}")

    await bot.process_commands(message)


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle component interactions - route to handlers."""
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get("custom_id") == "request_access":
            await handle_access_request(interaction)
            return
        if await handle_vote_interaction(interaction):
            return


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle slash command errors."""
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "❌ You don't have permission to use this command. This command requires administrator privileges.",
            ephemeral=True,
        )
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.",
            ephemeral=True,
        )
    elif isinstance(error, app_commands.errors.CommandNotFound):
        await interaction.response.send_message(
            "❓ Command not found. Use `/commands` to see available commands.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(error)}", ephemeral=True
        )
        print(f"Command error: {error}")
