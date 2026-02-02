"""Overseerr extension - user linking, API, and media request notifications."""

import json
import os
from typing import Any, Dict, List

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks

from ..bot import tree
from ..config import OVERSEERR_API_KEY, OVERSEERR_URL, TEST_GUILD_ID, USER_MAPPING_FILE

# Global cache for Overseerr users
overseerr_users_cache: List[Dict[str, Any]] = []


def save_user_mapping(discord_id: int, overseerr_username: str) -> bool:
    """Save a Discord user to Overseerr username mapping."""
    try:
        mappings = {}
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)

        mappings[overseerr_username.lower()] = discord_id

        os.makedirs(os.path.dirname(USER_MAPPING_FILE), exist_ok=True)
        with open(USER_MAPPING_FILE, "w") as f:
            json.dump(mappings, f)

        return True
    except Exception as e:
        print(f"Error saving user mapping: {e}")
        return False


def get_discord_id_for_overseerr_user(overseerr_username: str):
    """Get the Discord ID associated with an Overseerr username."""
    try:
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)
                return mappings.get(overseerr_username.lower())
    except Exception as e:
        print(f"Error loading user mapping: {e}")
    return None


def load_user_mappings() -> Dict[str, str]:
    """Load the Discord user to Overseerr username mappings (discord_id -> username)."""
    try:
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)

            converted_mappings = {}
            for username, discord_id in mappings.items():
                converted_mappings[str(discord_id)] = username

            return converted_mappings
        return {}
    except Exception as e:
        print(f"Error loading user mappings: {e}")
        return {}


async def get_overseerr_users() -> List[Dict[str, Any]]:
    """Fetch all users from Overseerr API."""
    if not OVERSEERR_API_KEY:
        return []

    headers = {"X-Api-Key": OVERSEERR_API_KEY, "Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{OVERSEERR_URL}/api/v1/user?take=100&skip=0", headers=headers
            ) as response:
                if response.status != 200:
                    print(f"Error fetching users: {response.status}")
                    return []

                data = await response.json()
                total_pages = data.get("pageInfo", {}).get("pages", 1)
                all_users = data.get("results", [])

                for page in range(1, total_pages):
                    async with session.get(
                        f"{OVERSEERR_URL}/api/v1/user?take=100&skip={page*100}",
                        headers=headers,
                    ) as page_response:
                        if page_response.status == 200:
                            page_data = await page_response.json()
                            all_users.extend(page_data.get("results", []))

                return all_users
        except Exception as e:
            print(f"Error fetching Overseerr users: {e}")
            return []


async def overseerr_username_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Autocomplete for Overseerr usernames."""
    choices = []

    if not overseerr_users_cache:
        try:
            users = await get_overseerr_users()
            for user in users:
                if (
                    current.lower() in user.get("displayName", "").lower()
                    or current.lower() in user.get("email", "").lower()
                ):
                    choices.append(
                        app_commands.Choice(
                            name=user.get("displayName", ""),
                            value=user.get("displayName", ""),
                        )
                    )
                    if len(choices) >= 25:
                        break
        except Exception as e:
            print(f"Error in autocomplete: {e}")
    else:
        for user in overseerr_users_cache:
            if (
                current.lower() in user.get("displayName", "").lower()
                or current.lower() in user.get("email", "").lower()
            ):
                choices.append(
                    app_commands.Choice(
                        name=user.get("displayName", ""),
                        value=user.get("displayName", ""),
                    )
                )
                if len(choices) >= 25:
                    break

    return choices


async def is_linked_to_overseerr(discord_id: int) -> bool:
    """Check if a Discord user has linked their Overseerr account."""
    try:
        mappings = load_user_mappings()
        return str(discord_id) in mappings
    except Exception as e:
        print(f"Error checking if user is linked: {e}")
        return False


def get_overseerr_username(discord_id: int) -> str:
    """Get the Overseerr username for a Discord user ID."""
    try:
        mappings = load_user_mappings()
        return mappings.get(str(discord_id))
    except Exception as e:
        print(f"Error retrieving Overseerr username: {e}")
        return None


def get_discord_id_by_overseerr_username(overseerr_username: str) -> int:
    """Get the Discord user ID for an Overseerr username."""
    try:
        mappings = load_user_mappings()
        for discord_id, username in mappings.items():
            if username.lower() == overseerr_username.lower():
                return int(discord_id)
        return None
    except Exception as e:
        print(f"Error retrieving Discord ID: {e}")
        return None


@tasks.loop(hours=1)
async def cache_overseerr_users():
    """Cache Overseerr users every hour."""
    global overseerr_users_cache
    try:
        overseerr_users = await get_overseerr_users()
        overseerr_users_cache = overseerr_users
        print(f"Cached {len(overseerr_users)} Overseerr users")
    except Exception as e:
        print(f"Error caching Overseerr users: {e}")


def create_overseerr_embed():
    """Create the Overseerr guide embed."""
    embed = discord.Embed(
        title="🎬 Media Request Guide | Guide de Demande de Média", color=0x00B8FF
    )

    embed.add_field(
        name="🇺🇸 How to Request Media",
        value=(
            "Welcome to the Overseerr request channel! 🎬\n"
            "Here you can request movies or TV shows you'd like to see on the media server (Plex).\n\n"
            "📍 To make a request:\n"
            "1. Visit [Overseerr](https://overseer.tessdev.fr)\n"
            "2. Log in using your **Discord** account\n"
            "3. Use the search bar to find the movie or series you want\n"
            '4. Click on **"Request"** — and you\'re done!\n\n'
            "💡 Once approved, your request will be downloaded and added to the server automatically.\n\n"
            "If you need help, feel free to ask in this channel or contact an admin.\n"
            "Enjoy! 🍿\n\n"
        ),
        inline=False,
    )

    embed.add_field(
        name="\n🇫🇷 Comment faire une demande de contenu",
        value=(
            "Bienvenue sur le canal de demande Overseerr ! 🎬\n"
            "Ici, vous pouvez demander des **films ou séries** que vous souhaitez voir sur le serveur média (Plex).\n\n"
            "📍 Pour faire une demande :\n"
            "1. Allez sur [Overseerr](https://overseer.tessdev.fr)\n"
            "2. Connectez-vous avec votre **compte Discord**\n"
            "3. Utilisez la barre de recherche pour trouver le film ou la série souhaité(e)\n"
            '4. Cliquez sur **"Demander"** — et c\'est terminé !\n\n'
            "💡 Une fois approuvée, votre demande sera automatiquement téléchargée et ajoutée au serveur.\n\n"
            "Si vous avez besoin d'aide, posez votre question ici ou contactez un admin.\n"
            "Bon visionnage ! 🍿"
        ),
        inline=False,
    )

    return embed


class OverseerrView(discord.ui.View):
    """View with button linking to Overseerr."""

    def __init__(self):
        super().__init__(timeout=None)
        overseerr_button = discord.ui.Button(
            label="🔍 Go to Overseerr | Aller à Overseerr",
            style=discord.ButtonStyle.link,
            url="https://overseer.tessdev.fr",
        )
        self.add_item(overseerr_button)


@tree.command(
    name="list_overseerr_links",
    description="List all Discord to Overseerr account links (Admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def list_overseerr_links(interaction: discord.Interaction):
    """List all Discord to Overseerr account links."""
    await interaction.response.defer(ephemeral=True)

    try:
        mappings = {}
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)

        if not mappings:
            await interaction.followup.send(
                "No Discord to Overseerr account links found.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Discord to Overseerr Account Links",
            description="Below are all the current account links:",
            color=0x00B8FF,
        )

        for overseerr_user, discord_id in mappings.items():
            try:
                member = await interaction.guild.fetch_member(int(discord_id))
                member_name = (
                    member.display_name if member else f"Unknown User ({discord_id})"
                )
                embed.add_field(
                    name=f"Overseerr: {overseerr_user}",
                    value=f"Discord: {member_name} ({discord_id})",
                    inline=False,
                )
            except Exception as e:
                embed.add_field(
                    name=f"Overseerr: {overseerr_user}",
                    value=f"Discord: Unknown User ({discord_id}) - Error: {str(e)}",
                    inline=False,
                )

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="link_overseerr",
    description="Link your Discord account to your Overseerr username for notifications",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.autocomplete(overseerr_username=overseerr_username_autocomplete)
async def link_overseerr(interaction: discord.Interaction, overseerr_username: str):
    """Link Discord account to Overseerr username."""
    await interaction.response.defer(ephemeral=True)

    try:
        discord_id = interaction.user.id
        success = save_user_mapping(discord_id, overseerr_username)

        if success:
            embed = discord.Embed(
                title="✅ Account Linked | Compte Lié",
                description=(
                    f"🇺🇸 Your Discord account has been linked to Overseerr username: **{overseerr_username}**\n"
                    f"You will now be notified when your requested content becomes available.\n\n"
                    f"🇫🇷 Votre compte Discord a été lié au nom d'utilisateur Overseerr: **{overseerr_username}**\n"
                    f"Vous serez désormais notifié lorsque votre contenu demandé sera disponible."
                ),
                color=0x00B8FF,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Error saving your username mapping. Please try again.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="unlink_overseerr",
    description="Unlink your Discord account from your Overseerr username",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.autocomplete(overseerr_username=overseerr_username_autocomplete)
async def unlink_overseerr(interaction: discord.Interaction, overseerr_username: str):
    """Unlink Discord account from Overseerr username."""
    await interaction.response.defer(ephemeral=True)

    try:
        mappings = {}
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)

        if overseerr_username.lower() in mappings:
            if str(mappings[overseerr_username.lower()]) == str(interaction.user.id):
                del mappings[overseerr_username.lower()]
                with open(USER_MAPPING_FILE, "w") as f:
                    json.dump(mappings, f)

                embed = discord.Embed(
                    title="✅ Account Unlinked | Compte Délié",
                    description=(
                        f"🇺🇸 Your Discord account has been unlinked from Overseerr username: **{overseerr_username}**\n"
                        f"You will no longer receive notifications for this account.\n\n"
                        f"🇫🇷 Votre compte Discord a été délié du nom d'utilisateur Overseerr: **{overseerr_username}**\n"
                        f"Vous ne recevrez plus de notifications pour ce compte."
                    ),
                    color=0x00B8FF,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ This Overseerr username is linked to a different Discord account.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                "❌ No link found for this Overseerr username.", ephemeral=True
            )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="overseerr_status",
    description="Check if your Discord account is linked to Overseerr",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def overseerr_status(interaction: discord.Interaction):
    """Check Overseerr link status."""
    await interaction.response.defer(ephemeral=True)

    is_linked = await is_linked_to_overseerr(interaction.user.id)

    if is_linked:
        username = get_overseerr_username(interaction.user.id)
        await interaction.followup.send(
            f"✅ Your Discord account is linked to the Overseerr user: **{username}**",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            "❌ Your Discord account is not linked to any Overseerr account. Use `/link_overseerr` to link your account.",
            ephemeral=True,
        )


@tree.command(
    name="send_overseerr_embed",
    description="Send the Overseerr guide embed to the channel. (Only for admins)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def send_overseerr_embed(interaction: discord.Interaction):
    """Send Overseerr guide embed to current channel."""
    await interaction.response.defer(ephemeral=True)

    try:
        embed = create_overseerr_embed()
        view = OverseerrView()
        await interaction.channel.send(embed=embed, view=view)

        await interaction.followup.send(
            "✅ Overseerr guide embed sent successfully!", ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="admin_link_overseerr",
    description="[ADMIN] Link another user's Discord account to an Overseerr username",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(overseerr_username=overseerr_username_autocomplete)
async def admin_link_overseerr(
    interaction: discord.Interaction,
    discord_user: discord.Member,
    overseerr_username: str,
):
    """Admin: Link another user's Discord to Overseerr."""
    await interaction.response.defer(ephemeral=True)

    try:
        discord_id = discord_user.id
        success = save_user_mapping(discord_id, overseerr_username)

        if success:
            embed = discord.Embed(
                title="✅ Account Linked by Admin",
                description=(
                    f"Discord user **{discord_user.display_name}** has been linked to Overseerr username: **{overseerr_username}**\n"
                    f"They will now receive notifications when their requested content becomes available.\n\n"
                    f"Note: You can link any valid Overseerr username, even if it doesn't appear in the autocomplete list."
                ),
                color=0x00B8FF,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Error saving the username mapping. Please try again.",
                ephemeral=True,
            )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="admin_unlink_overseerr",
    description="[ADMIN] Unlink another user's Discord account from an Overseerr username",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(overseerr_username=overseerr_username_autocomplete)
async def admin_unlink_overseerr(
    interaction: discord.Interaction,
    discord_user: discord.Member,
    overseerr_username: str,
):
    """Admin: Unlink another user's Discord from Overseerr."""
    await interaction.response.defer(ephemeral=True)

    try:
        mappings = {}
        if os.path.exists(USER_MAPPING_FILE):
            with open(USER_MAPPING_FILE, "r") as f:
                mappings = json.load(f)

        if overseerr_username.lower() in mappings:
            if str(mappings[overseerr_username.lower()]) == str(discord_user.id):
                del mappings[overseerr_username.lower()]
                with open(USER_MAPPING_FILE, "w") as f:
                    json.dump(mappings, f)

                embed = discord.Embed(
                    title="✅ Account Unlinked by Admin",
                    description=(
                        f"Discord user **{discord_user.display_name}** has been unlinked from Overseerr username: **{overseerr_username}**\n"
                        f"They will no longer receive notifications for this account."
                    ),
                    color=0x00B8FF,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ This Overseerr username is not linked to the specified Discord user.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                "❌ No link found for this Overseerr username.", ephemeral=True
            )
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(
    name="admin_find_user",
    description="[ADMIN] Find a Discord user by username for linking/unlinking",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
async def admin_find_user(interaction: discord.Interaction, search_term: str):
    """Admin: Search for Discord users by username."""
    await interaction.response.defer(ephemeral=True)

    try:
        guild = interaction.guild
        matching_members = [
            member
            for member in guild.members
            if search_term.lower() in member.display_name.lower()
            or (member.nick and search_term.lower() in member.nick.lower())
            or search_term.lower() in str(member).lower()
        ]

        if not matching_members:
            await interaction.followup.send(
                f"❌ No users found matching: '{search_term}'", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Discord Users Matching: '{search_term}'",
            description=f"Found {len(matching_members)} users. Use these with admin_link_overseerr and admin_unlink_overseerr commands.",
            color=0x00B8FF,
        )

        for member in matching_members[:20]:
            embed.add_field(
                name=f"{member.display_name} ({member})",
                value=f"ID: {member.id}",
                inline=False,
            )

        if len(matching_members) > 20:
            embed.set_footer(
                text=f"Showing 20 of {len(matching_members)} results. Please refine your search for more specific results."
            )

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
