"""Plex extension - media statistics from Plex server."""

import time
from datetime import datetime, timedelta

import discord
from discord import app_commands
from plexapi.server import PlexServer

from ..bot import tree
from ..config import PLEX_TOKEN, PLEX_URL, TEST_GUILD_ID


def get_plex_connection():
    """Create a connection to Plex server."""
    try:
        return PlexServer(PLEX_URL, PLEX_TOKEN)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None


@tree.command(
    name="media_stats",
    description="Show statistics for Movies, TV Shows, Anime Shows, and Anime Movies",
    guild=discord.Object(id=TEST_GUILD_ID),
)
async def media_stats(interaction: discord.Interaction):
    """Display media library statistics from Plex."""
    await interaction.response.defer(ephemeral=True)

    plex_server = get_plex_connection()
    if not plex_server:
        await interaction.followup.send(
            "❌ Could not connect to Plex server. Please check your configuration.",
            ephemeral=True,
        )
        return

    try:
        embed = discord.Embed(
            title="📊 Media Library Statistics",
            description="Statistics from your Plex Libraries",
            color=0x1F2033,
        )

        library_names = ["Movies", "TV Shows", "Anime Shows", "Anime Movies"]
        library_stats = {}
        recent_items = []

        total_items = 0
        total_size_gb = 0
        total_duration_minutes = 0
        total_episodes = 0
        recent_date = datetime.now() - timedelta(days=7)

        for library_name in library_names:
            try:
                library = plex_server.library.section(library_name)
                library_items = library.all()
                item_count = len(library_items)
                total_items += item_count

                library_size_gb = 0
                duration_minutes = 0
                recent_count = 0
                episode_count = 0

                if "movie" in library_name.lower():
                    for movie in library_items:
                        try:
                            if hasattr(movie, "media") and movie.media:
                                library_size_gb += movie.media[0].parts[0].size / (1024**3)
                            if hasattr(movie, "duration"):
                                duration_minutes += movie.duration / 60000
                            if hasattr(movie, "addedAt") and movie.addedAt >= recent_date:
                                recent_count += 1
                                recent_items.append(
                                    (movie.title, library_name, movie.year, movie.addedAt)
                                )
                        except Exception as e:
                            print(f"Skipping movie {getattr(movie, 'title', 'unknown')}: {e}")

                    days = int(duration_minutes // 1440)
                    hours = int((duration_minutes % 1440) // 60)
                    minutes = int(duration_minutes % 60)

                    library_stats[library_name] = {
                        "count": item_count,
                        "size_gb": library_size_gb,
                        "duration": f"{days}d {hours}h {minutes}m",
                        "duration_minutes": duration_minutes,
                        "recent_count": recent_count,
                        "type": "movie",
                    }

                elif "show" in library_name.lower():
                    for show in library_items:
                        try:
                            episodes = show.episodes()
                            episode_count += len(episodes)
                            for episode in episodes:
                                try:
                                    if hasattr(episode, "media") and episode.media:
                                        library_size_gb += (
                                            episode.media[0].parts[0].size / (1024**3)
                                        )
                                    if hasattr(episode, "duration"):
                                        duration_minutes += episode.duration / 60000
                                except Exception as e:
                                    print(f"Skipping episode in {getattr(show, 'title', 'unknown')}: {e}")
                            if hasattr(show, "addedAt") and show.addedAt >= recent_date:
                                recent_count += 1
                                recent_items.append(
                                    (
                                        show.title,
                                        library_name,
                                        len(episodes),
                                        show.addedAt,
                                    )
                                )
                        except Exception as e:
                            print(f"Skipping show {getattr(show, 'title', 'unknown')}: {e}")

                    days = int(duration_minutes // 1440)
                    hours = int((duration_minutes % 1440) // 60)
                    minutes = int(duration_minutes % 60)

                    library_stats[library_name] = {
                        "count": item_count,
                        "episodes": episode_count,
                        "size_gb": library_size_gb,
                        "duration": f"{days}d {hours}h {minutes}m",
                        "duration_minutes": duration_minutes,
                        "recent_count": recent_count,
                        "type": "show",
                    }

                total_size_gb += library_size_gb
                total_duration_minutes += duration_minutes
                total_episodes += episode_count

            except Exception as e:
                embed.add_field(
                    name=f"❌ Error processing {library_name}",
                    value=f"Error: {str(e)}",
                    inline=False,
                )

        total_days = int(total_duration_minutes // 1440)
        total_hours = int((total_duration_minutes % 1440) // 60)
        total_minutes = int(total_duration_minutes % 60)

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

        for name, stats in library_stats.items():
            if stats["type"] == "movie":
                if name == "Movies":
                    emoji = "🎬"
                    display_name = "MOVIES"
                    color = "35"
                else:
                    emoji = "🇯🇵"
                    display_name = "ANIME MOVIES"
                    color = "35;1"

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
            else:
                if name == "TV Shows":
                    emoji = "📺"
                    display_name = "TV SHOWS"
                    color = "36"
                else:
                    emoji = "🇯🇵"
                    display_name = "ANIME SHOWS"
                    color = "36;1"

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

        embed.add_field(name="", value="───────────────────────", inline=False)

        if recent_items:
            recent_items.sort(key=lambda x: x[3], reverse=True)
            recent_content = "```ansi\n\u001b[1;35mRECENT ADDITIONS\u001b[0m\n"

            for title, lib_type, year_or_eps, _ in recent_items[:6]:
                if "movie" in lib_type.lower():
                    recent_content += (
                        f"• \u001b[1;36m{title}\u001b[0m - {lib_type} ({year_or_eps})\n"
                    )
                else:
                    recent_content += (
                        f"• \u001b[1;36m{title}\u001b[0m - {lib_type} ({year_or_eps} eps)\n"
                    )

            recent_content += "```"
            embed.add_field(name="", value=recent_content, inline=False)

        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(
            text=f"📊 Stats as of {current_time} • Use /media_stats to refresh"
        )

        embed.set_thumbnail(
            url="https://cdn.iconscout.com/icon/free/png-256/plex-3521495-2944935.png"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to fetch media statistics:\n```{str(e)}```",
            color=0xFF0000,
        )
        await interaction.followup.send(embed=error_embed, ephemeral=True)
