"""Media voting deletion extension - vote to delete unwatched media via Radarr/Sonarr."""

import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from plexapi.server import PlexServer

from ..bot import tree
from ..config import (
    AUTO_VOTE_LAST_RUN_FILE,
    AUTO_VOTE_UNWATCHED_DAYS,
    MEDIA_VOTES_DRY_RUN,
    MEDIA_VOTES_FILE,
    VOTE_MENTION_ROLE_ID,
    PLEX_TOKEN,
    PLEX_URL,
    RADARR_API_KEY,
    RADARR_URL,
    SONARR_API_KEY,
    SONARR_URL,
    TEST_GUILD_ID,
    VOTE_CHANNEL_ID,
    VOTE_DURATION_DAYS,
)


# --- Radarr/Sonarr API helpers ---


def _extract_tmdb_id(plex_item) -> Optional[int]:
    """Extract tmdbId from Plex movie guids."""
    if not hasattr(plex_item, "guids") or not plex_item.guids:
        if hasattr(plex_item, "guid") and plex_item.guid:
            match = re.search(r"tmdb://(\d+)", plex_item.guid)
            if match:
                return int(match.group(1))
        return None
    for g in plex_item.guids:
        if hasattr(g, "id") and g.id and "tmdb" in g.id.lower():
            match = re.search(r"(\d+)", g.id)
            if match:
                return int(match.group(1))
    return None


def _extract_tvdb_id(plex_item) -> Optional[int]:
    """Extract tvdbId from Plex show guids."""
    if not hasattr(plex_item, "guids") or not plex_item.guids:
        if hasattr(plex_item, "guid") and plex_item.guid:
            match = re.search(r"tvdb://(\d+)", plex_item.guid)
            if match:
                return int(match.group(1))
        return None
    for g in plex_item.guids:
        if hasattr(g, "id") and g.id and "tvdb" in g.id.lower():
            match = re.search(r"(\d+)", g.id)
            if match:
                return int(match.group(1))
    return None


async def get_radarr_movie_by_tmdb(tmdb_id: int) -> Optional[dict]:
    """Find Radarr movie by tmdbId. Returns movie dict or None."""
    if not RADARR_URL or not RADARR_API_KEY:
        return None
    url = f"{RADARR_URL.rstrip('/')}/api/v3/movie"
    headers = {"X-Api-Key": RADARR_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            for m in data:
                if m.get("tmdbId") == tmdb_id:
                    return m
    return None


async def get_sonarr_series_by_tvdb(tvdb_id: int) -> Optional[dict]:
    """Find Sonarr series by tvdbId. Returns series dict or None."""
    if not SONARR_URL or not SONARR_API_KEY:
        return None
    url = f"{SONARR_URL.rstrip('/')}/api/v3/series"
    headers = {"X-Api-Key": SONARR_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            for s in data:
                if s.get("tvdbId") == tvdb_id:
                    return s
    return None


async def delete_radarr_movie(radarr_id: int) -> bool:
    """Delete movie from Radarr with files. Returns True on success."""
    if not RADARR_URL or not RADARR_API_KEY:
        return False
    url = f"{RADARR_URL.rstrip('/')}/api/v3/movie/{radarr_id}"
    params = {"deleteFiles": "true"}
    headers = {"X-Api-Key": RADARR_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, params=params, headers=headers) as resp:
            return resp.status in (200, 204)


async def delete_sonarr_series(sonarr_id: int) -> bool:
    """Delete series from Sonarr with files. Returns True on success."""
    if not SONARR_URL or not SONARR_API_KEY:
        return False
    url = f"{SONARR_URL.rstrip('/')}/api/v3/series/{sonarr_id}"
    params = {"deleteFiles": "true"}
    headers = {"X-Api-Key": SONARR_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.delete(url, params=params, headers=headers) as resp:
            return resp.status in (200, 204)


# --- Vote persistence ---


def _ensure_data_dir():
    d = os.path.dirname(MEDIA_VOTES_FILE)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def load_votes() -> dict:
    """Load vote state from file."""
    _ensure_data_dir()
    if not os.path.exists(MEDIA_VOTES_FILE):
        return {"votes": {}}
    try:
        with open(MEDIA_VOTES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"votes": {}}


def save_votes(data: dict):
    """Save vote state to file."""
    _ensure_data_dir()
    with open(MEDIA_VOTES_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- Plex helpers ---


def get_plex_connection():
    """Create a connection to Plex server."""
    try:
        return PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None


def search_plex_media(query: str) -> List[dict]:
    """Search all media libraries for query. Returns list of media info dicts."""
    plex = get_plex_connection()
    if not plex:
        return []
    results = []
    library_names = ["Movies", "TV Shows", "Anime Shows", "Anime Movies"]
    seen_keys = set()
    for lib_name in library_names:
        try:
            lib = plex.library.section(lib_name)
            items = lib.search(query, maxresults=25)
            for item in items:
                key = str(item.ratingKey)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                info = _plex_item_to_info(item, lib_name)
                if info:
                    results.append(info)
        except Exception as e:
            print(f"Error searching {lib_name}: {e}")
    return results[:25]


def _plex_item_to_info(item, library: str) -> Optional[dict]:
    """Convert Plex item to media info dict for vote creation."""
    try:
        item.reload()
    except Exception:
        pass
    is_movie = "movie" in library.lower()
    title = getattr(item, "title", None) or "Unknown"
    year = getattr(item, "year", None)
    rating_key = str(item.ratingKey)
    added_at = getattr(item, "addedAt", None)
    last_viewed = getattr(item, "lastViewedAt", None)
    size_gb = 0.0
    try:
        if is_movie:
            if hasattr(item, "media") and item.media and item.media[0].parts:
                size_gb = item.media[0].parts[0].size / (1024**3)
        else:
            for ep in item.episodes():
                try:
                    if hasattr(ep, "media") and ep.media and ep.media[0].parts:
                        size_gb += ep.media[0].parts[0].size / (1024**3)
                except Exception:
                    pass
    except Exception:
        pass
    if is_movie:
        tmdb_id = _extract_tmdb_id(item)
        return {
            "media_type": "movie",
            "plex_rating_key": rating_key,
            "tmdb_id": tmdb_id,
            "title": f"{title} ({year})" if year else title,
            "library": library,
            "size_gb": round(size_gb, 2),
            "added_at": added_at.isoformat() if added_at else None,
            "last_viewed": last_viewed.isoformat() if last_viewed else None,
        }
    else:
        tvdb_id = _extract_tvdb_id(item)
        return {
            "media_type": "show",
            "plex_rating_key": rating_key,
            "tvdb_id": tvdb_id,
            "title": f"{title} ({year})" if year else title,
            "library": library,
            "size_gb": round(size_gb, 2),
            "added_at": added_at.isoformat() if added_at else None,
            "last_viewed": last_viewed.isoformat() if last_viewed else None,
        }


# --- Vote embed and view ---


def _format_voters(user_ids: list) -> str:
    """Format voter list as Discord mentions. Truncate if too long."""
    if not user_ids:
        return "(none)"
    mentions = ", ".join(f"<@{uid}>" for uid in user_ids)
    if len(mentions) > 900:
        return mentions[:897] + "..."
    return mentions


def _format_date(value: Optional[str]) -> str:
    """Format ISO date string for display (e.g. 2024-01-15 -> Jan 15, 2024)."""
    if not value:
        return "Unknown"
    s = value[:10] if isinstance(value, str) else str(value)[:10]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return s


def _vote_key(message_id: str, channel_id: str) -> str:
    return f"msg_{message_id}_ch_{channel_id}"


def _build_vote_embed(
    vote_data: dict,
    status: Optional[str] = None,
) -> discord.Embed:
    """Build vote embed from vote data."""
    title = vote_data.get("title", "Unknown")
    library = vote_data.get("library", "Unknown")
    size_gb = vote_data.get("size_gb", 0)
    added_at = vote_data.get("added_at")
    last_viewed = vote_data.get("last_viewed")
    keep_voters = vote_data.get("keep_voters", [])
    delete_voters = vote_data.get("delete_voters", [])
    ends_at = vote_data.get("ends_at")
    created_at = vote_data.get("created_at")

    last_watched_str = "Never" if not last_viewed else _format_date(last_viewed)
    added_str = _format_date(added_at) if added_at else "Unknown"

    embed = discord.Embed(
        title=f"Vote: Delete {title}?",
        color=0x5865F2,
        timestamp=datetime.fromisoformat(created_at) if created_at else datetime.now(),
    )
    keep_str = f"{len(keep_voters)} — {_format_voters(keep_voters)}"
    delete_str = f"{len(delete_voters)} — {_format_voters(delete_voters)}"
    embed.add_field(name="Library", value=library, inline=True)
    embed.add_field(name="Size", value=f"{size_gb} GB", inline=True)
    embed.add_field(name="Last watched", value=last_watched_str, inline=True)
    embed.add_field(name="Added", value=added_str, inline=True)
    embed.add_field(name="Keep votes", value=keep_str, inline=False)
    embed.add_field(name="Delete votes", value=delete_str, inline=False)

    if status:
        if status == "kept":
            embed.color = 0x57F287
        elif status == "deleted":
            embed.color = 0xED4245
        elif "dry run" in status.lower():
            embed.color = 0xFEE75C
        else:
            embed.color = 0x5865F2
        embed.add_field(name="Status", value=status.capitalize(), inline=False)
    elif (vote_data.get("media_type") == "movie" and not vote_data.get("radarr_id")) or (
        vote_data.get("media_type") == "show" and not vote_data.get("sonarr_id")
    ):
        embed.add_field(
            name="⚠️ Note",
            value="Not managed by Radarr/Sonarr - cannot delete",
            inline=False,
        )
    if ends_at and not status:
        try:
            end_dt = datetime.fromisoformat(ends_at)
            days_left = (end_dt - datetime.now(end_dt.tzinfo) if end_dt.tzinfo else end_dt - datetime.now()).days
            embed.set_footer(text=f"Vote ends in {days_left} days" if days_left > 0 else f"Ends: {ends_at[:10]}")
        except Exception:
            embed.set_footer(text=f"Ends: {ends_at[:10]}")

    return embed


class VoteView(discord.ui.View):
    """View with Keep and Delete buttons for media votes. Handled via on_interaction (no callbacks)."""

    def __init__(self, vote_key: str):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(label="Keep", style=discord.ButtonStyle.success, custom_id=f"vote_keep_{vote_key}")
        )
        self.add_item(
            discord.ui.Button(label="Delete", style=discord.ButtonStyle.danger, custom_id=f"vote_delete_{vote_key}")
        )


async def _handle_vote(interaction: discord.Interaction, vote_key: str, vote_type: str):
    """Handle Keep or Delete button press."""
    data = load_votes()
    votes = data.get("votes", {})
    if vote_key not in votes:
        await interaction.response.send_message("This vote has expired or been cancelled.", ephemeral=True)
        return
    vote = votes[vote_key]
    user_id = str(interaction.user.id)
    keep_voters = vote.get("keep_voters", [])
    delete_voters = vote.get("delete_voters", [])

    if vote_type == "keep":
        if user_id in delete_voters:
            delete_voters.remove(user_id)
        if user_id not in keep_voters:
            keep_voters.append(user_id)
    else:
        if user_id in keep_voters:
            keep_voters.remove(user_id)
        if user_id not in delete_voters:
            delete_voters.append(user_id)

    vote["keep_voters"] = keep_voters
    vote["delete_voters"] = delete_voters
    save_votes(data)

    embed = _build_vote_embed(vote)
    await interaction.response.edit_message(embed=embed, view=VoteView(vote_key))
    await interaction.followup.send("Vote recorded!", ephemeral=True)


def _create_vote_view(vote_key: str) -> VoteView:
    """Create a VoteView with proper custom_ids for persistence."""
    return VoteView(vote_key)


# --- Resolution logic ---


async def _apply_vote_result(vote: dict, message: discord.Message) -> str:
    """Apply vote result (kept or delete) and edit the message. Returns status string."""
    keep_voters = vote.get("keep_voters", [])
    if len(keep_voters) > 0:
        embed = _build_vote_embed(vote, status="kept")
        view = discord.ui.View()
        view.stop()
        await message.edit(embed=embed, view=view)
        return "kept"
    deleted = False
    if MEDIA_VOTES_DRY_RUN:
        status = "would have been deleted (dry run)"
    else:
        media_type = vote.get("media_type", "")
        if media_type == "movie" and vote.get("radarr_id"):
            deleted = await delete_radarr_movie(vote["radarr_id"])
        elif media_type == "show" and vote.get("sonarr_id"):
            deleted = await delete_sonarr_series(vote["sonarr_id"])
        status = "deleted" if deleted else "skipped (not in Radarr/Sonarr)"
    embed = _build_vote_embed(vote, status=status)
    view = discord.ui.View()
    view.stop()
    await message.edit(embed=embed, view=view)
    return status


@tasks.loop(hours=1)
async def resolve_expired_votes():
    """Check expired votes and delete or mark kept."""
    data = load_votes()
    votes = data.get("votes", {})
    now = datetime.utcnow()
    to_remove = []
    for key, vote in list(votes.items()):
        ends_at_str = vote.get("ends_at")
        if not ends_at_str:
            continue
        try:
            ends_at = datetime.fromisoformat(ends_at_str.replace("Z", "+00:00"))
            if ends_at.tzinfo:
                ends_at = ends_at.replace(tzinfo=None)
        except Exception:
            continue
        if ends_at > now:
            continue
        channel_id = int(vote.get("channel_id", 0))
        message_id = int(vote.get("message_id", 0))
        if not channel_id or not message_id:
            to_remove.append(key)
            continue
        try:
            from ..bot import bot
            channel = await bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            to_remove.append(key)
            continue
        await _apply_vote_result(vote, message)
        to_remove.append(key)
    for key in to_remove:
        votes.pop(key, None)
    if to_remove:
        save_votes(data)


# --- Automated vote task ---


AUTO_VOTE_COOLDOWN_HOURS = 6 * 24  # 6 days


def _get_auto_vote_last_run() -> Optional[datetime]:
    """Get last auto vote run timestamp (naive UTC)."""
    if not os.path.exists(AUTO_VOTE_LAST_RUN_FILE):
        return None
    try:
        with open(AUTO_VOTE_LAST_RUN_FILE, "r") as f:
            data = json.load(f)
        s = data.get("last_run")
        if not s:
            return None
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (json.JSONDecodeError, IOError, ValueError):
        return None


def _set_auto_vote_last_run():
    """Save current time as last auto vote run."""
    _ensure_data_dir()
    with open(AUTO_VOTE_LAST_RUN_FILE, "w") as f:
        json.dump({"last_run": datetime.utcnow().isoformat()}, f)


@tasks.loop(hours=24)
async def auto_create_votes():
    """Find unwatched media and create vote embeds."""
    last_run = _get_auto_vote_last_run()
    if last_run:
        elapsed = (datetime.utcnow() - last_run).total_seconds() / 3600
        if elapsed < AUTO_VOTE_COOLDOWN_HOURS:
            return
    from ..bot import bot
    channel = bot.get_channel(VOTE_CHANNEL_ID) if VOTE_CHANNEL_ID else None
    if not channel:
        print("Warning: VOTE_CHANNEL_ID not set or channel not found, skipping auto votes")
        return
    plex = get_plex_connection()
    if not plex:
        return
    data = load_votes()
    votes = data.get("votes", {})
    active_rating_keys = set()
    for v in votes.values():
        active_rating_keys.add(v.get("plex_rating_key", ""))
    cutoff = datetime.utcnow() - timedelta(days=AUTO_VOTE_UNWATCHED_DAYS)
    added_cutoff = datetime.utcnow() - timedelta(days=30)
    library_names = ["Movies", "TV Shows", "Anime Shows", "Anime Movies"]
    candidates = []
    for lib_name in library_names:
        try:
            lib = plex.library.section(lib_name)
            items = lib.all()
            for item in items:
                if str(item.ratingKey) in active_rating_keys:
                    continue
                last_viewed = getattr(item, "lastViewedAt", None)
                if last_viewed and last_viewed.replace(tzinfo=None) > cutoff:
                    continue
                added_at = getattr(item, "addedAt", None)
                if added_at and added_at.replace(tzinfo=None) > added_cutoff:
                    continue
                info = _plex_item_to_info(item, lib_name)
                if info:
                    candidates.append(info)
                if len(candidates) >= 5:
                    break
            if len(candidates) >= 5:
                break
        except Exception as e:
            print(f"Error in auto vote for {lib_name}: {e}")
    batch = candidates[:5]
    if batch:
        intro = (
            "**Media deletion vote** — Unwatched media is up for removal. "
            "Click **Keep** to save it, **Delete** to remove it. "
            "When the vote ends, media with no Keep votes is deleted from the library."
        )
        if VOTE_MENTION_ROLE_ID and channel.guild:
            role = channel.guild.get_role(VOTE_MENTION_ROLE_ID)
            if role:
                await channel.send(f"{role.mention}\n\n{intro}")
            else:
                await channel.send(intro)
        else:
            await channel.send(intro)
    for info in batch:
        await _create_and_post_vote(bot, channel, info, data, mention_role=False)
        save_votes(data)
    if batch:
        _set_auto_vote_last_run()


async def _create_and_post_vote(
    bot: discord.Client,
    channel: discord.TextChannel,
    info: dict,
    data: dict,
    mention_role: bool = True,
) -> bool:
    """Create vote record and post embed. Returns True on success."""
    media_type = info.get("media_type", "")
    tmdb_id = info.get("tmdb_id")
    tvdb_id = info.get("tvdb_id")
    radarr_id = None
    sonarr_id = None
    title = info.get("title", "Unknown")
    added_at = info.get("added_at")
    if media_type == "movie" and tmdb_id:
        movie = await get_radarr_movie_by_tmdb(tmdb_id)
        if movie:
            radarr_id = movie.get("id")
            if movie.get("title"):
                year = movie.get("year")
                title = f"{movie['title']} ({year})" if year else movie["title"]
            if not added_at and movie.get("added"):
                added_at = movie["added"][:10] if isinstance(movie["added"], str) else None
    elif media_type == "show" and tvdb_id:
        series = await get_sonarr_series_by_tvdb(tvdb_id)
        if series:
            sonarr_id = series.get("id")
            if series.get("title"):
                year = series.get("year")
                title = f"{series['title']} ({year})" if year else series["title"]
            if not added_at and series.get("added"):
                added_at = series["added"][:10] if isinstance(series["added"], str) else None
    now = datetime.utcnow()
    ends_at = (now + timedelta(days=VOTE_DURATION_DAYS)).isoformat()
    vote_data = {
        "message_id": "",
        "channel_id": str(channel.id),
        "media_type": media_type,
        "plex_rating_key": info.get("plex_rating_key"),
        "tmdb_id": tmdb_id,
        "tvdb_id": tvdb_id,
        "radarr_id": radarr_id,
        "sonarr_id": sonarr_id,
        "title": title,
        "library": info.get("library", ""),
        "size_gb": info.get("size_gb", 0),
        "added_at": added_at[:10] if isinstance(added_at, str) else (added_at.isoformat()[:10] if added_at and hasattr(added_at, "isoformat") else None),
        "created_at": now.isoformat(),
        "ends_at": ends_at,
        "keep_voters": [],
        "delete_voters": [],
    }
    embed = _build_vote_embed(vote_data)
    content = None
    if mention_role and VOTE_MENTION_ROLE_ID and channel.guild:
        role = channel.guild.get_role(VOTE_MENTION_ROLE_ID)
        if role:
            content = role.mention
    msg = await channel.send(content=content, embed=embed)
    vote_key = _vote_key(str(msg.id), str(channel.id))
    vote_data["message_id"] = str(msg.id)
    view = _create_vote_view(vote_key)
    await msg.edit(view=view)
    data.setdefault("votes", {})[vote_key] = vote_data
    return True


# --- Commands ---


@tree.command(
    name="vote_delete",
    description="Search media by name and create a deletion vote",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(query="Search query for media (movie or show name)")
async def vote_delete(interaction: discord.Interaction, query: str):
    """Search Plex for media and create a vote embed."""
    await interaction.response.defer(ephemeral=True)
    results = search_plex_media(query)
    if not results:
        await interaction.followup.send(
            f"No media found for '{query}'. Try a different search term.",
            ephemeral=True,
        )
        return
    choices = [app_commands.Choice(name=r["title"][:100], value=str(i)) for i, r in enumerate(results[:25])]

    async def _select_callback(sel_interaction: discord.Interaction):
        if sel_interaction.user.id != interaction.user.id:
            await sel_interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return
        idx = int(sel_interaction.values[0])
        info = results[idx]
        channel = interaction.guild.get_channel(VOTE_CHANNEL_ID) if VOTE_CHANNEL_ID else None
        if not channel:
            await sel_interaction.response.edit_message(
                content="VOTE_CHANNEL_ID not set or channel not found. Set it in .env.",
                view=None,
            )
            return
        data = load_votes()
        await _create_and_post_vote(interaction.client, channel, info, data)
        save_votes(data)
        await sel_interaction.response.edit_message(
            content=f"Vote created for **{info['title']}** in {channel.mention}",
            view=None,
        )

    select = discord.ui.Select(
        placeholder="Choose media to vote on...",
        options=[discord.SelectOption(label=c.name[:100], value=c.value) for c in choices],
    )
    select.callback = _select_callback
    view = discord.ui.View()
    view.add_item(select)
    await interaction.followup.send(
        f"Found {len(results)} result(s). Select one to create a vote:",
        view=view,
        ephemeral=True,
    )


@tree.command(
    name="finish_vote",
    description="Finish a vote now and apply the result (admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message_id="The vote message ID (right-click message -> Copy ID)")
async def finish_vote(interaction: discord.Interaction, message_id: str):
    """Finish a vote immediately and apply the result (keep or delete)."""
    await interaction.response.defer(ephemeral=True)
    data = load_votes()
    votes = data.get("votes", {})
    found = None
    for key, vote in votes.items():
        if vote.get("message_id") == message_id:
            found = key
            break
    if not found:
        await interaction.followup.send("Vote not found or already resolved.", ephemeral=True)
        return
    vote = votes[found]
    channel_id = int(vote.get("channel_id", 0))
    try:
        channel = await interaction.client.fetch_channel(channel_id)
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        await interaction.followup.send("Vote message not found.", ephemeral=True)
        return
    status = await _apply_vote_result(vote, message)
    del votes[found]
    save_votes(data)
    await interaction.followup.send(f"Vote finished. Result: **{status}**.", ephemeral=True)


@tree.command(
    name="cancel_vote",
    description="Cancel an active vote (admin only)",
    guild=discord.Object(id=TEST_GUILD_ID),
)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message_id="The vote message ID (right-click message -> Copy ID)")
async def cancel_vote(interaction: discord.Interaction, message_id: str):
    """Cancel an active vote."""
    await interaction.response.defer(ephemeral=True)
    data = load_votes()
    votes = data.get("votes", {})
    found = None
    for key, vote in votes.items():
        if vote.get("message_id") == message_id:
            found = key
            break
    if not found:
        await interaction.followup.send("Vote not found or already resolved.", ephemeral=True)
        return
    channel_id = int(votes[found].get("channel_id", 0))
    try:
        channel = await interaction.client.fetch_channel(channel_id)
        message = await channel.fetch_message(int(message_id))
        embed = _build_vote_embed(votes[found], status="cancelled")
        await message.edit(embed=embed, view=discord.ui.View())
    except discord.NotFound:
        pass
    del votes[found]
    save_votes(data)
    await interaction.followup.send("Vote cancelled.", ephemeral=True)


# --- Interaction routing (called from events.py) ---


async def handle_vote_interaction(interaction: discord.Interaction) -> bool:
    """Handle vote button interactions. Returns True if handled."""
    if interaction.type != discord.InteractionType.component:
        return False
    custom_id = interaction.data.get("custom_id", "")
    if custom_id.startswith("vote_keep_") or custom_id.startswith("vote_delete_"):
        parts = custom_id.split("_", 2)
        if len(parts) >= 3:
            vote_key = parts[2]
            vote_type = "keep" if "keep" in custom_id else "delete"
            await _handle_vote(interaction, vote_key, vote_type)
            return True
    return False
