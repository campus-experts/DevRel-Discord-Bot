"""
bot/cogs/youtube_watcher.py – Discord cog that watches the GitHub YouTube channel.

How it works
────────────
1. On startup the cog loads the last-seen video ID from ``data/state.json``
   (created automatically; ignored by .gitignore).
2. A background ``discord.ext.tasks`` loop polls the YouTube Data API v3
   every ``check_interval_minutes`` minutes (configured in config.yaml).
3. Any video whose ID hasn't been seen before is posted to the configured
   Discord channel as a rich embed that includes:
     - Video title (linked to YouTube)
     - First 500 characters of the video description
     - Publish date
     - High-quality thumbnail
4. The newest video ID is saved to state.json so the bot does not
   re-announce the same video after a restart.

Environment variables required
───────────────────────────────
  YOUTUBE_API_KEY  – YouTube Data API v3 key (set in .env or host secrets)

config.yaml keys used (under ``youtube:``)
───────────────────────────────────────────
  channel_id              – YouTube channel ID to watch
  discord_channel_id      – Discord channel ID to post announcements in
  check_interval_minutes  – Poll interval (default: 30)
  max_results             – Videos per API call (default: 5)
"""

import logging
import os

import discord
from discord.ext import commands, tasks

from utils.state import load_state, save_state
from utils.youtube_api import YouTubeClient

logger = logging.getLogger(__name__)


class YouTubeWatcher(commands.Cog):
    """Background task that announces new GitHub YouTube videos."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cfg = bot.config["youtube"]

        self.yt_channel_id: str = cfg["channel_id"]
        self.discord_channel_id: int = int(cfg["discord_channel_id"])
        self.max_results: int = cfg.get("max_results", 5)
        interval: int = cfg.get("check_interval_minutes", 30)

        api_key = os.environ["YOUTUBE_API_KEY"]
        self.yt_client = YouTubeClient(api_key=api_key)

        self.state: dict = load_state()

        # Adjust the loop interval before starting it.
        self.check_youtube.change_interval(minutes=interval)
        self.check_youtube.start()

    def cog_unload(self) -> None:
        """Clean up the background task when the cog is unloaded."""
        self.check_youtube.cancel()

    # ------------------------------------------------------------------
    # Background task
    # ------------------------------------------------------------------

    @tasks.loop(minutes=30)  # default; overridden in __init__ via change_interval
    async def check_youtube(self) -> None:
        """Poll YouTube for new videos and post announcements."""
        logger.info("Polling YouTube channel: %s", self.yt_channel_id)

        videos = self.yt_client.get_recent_videos(
            self.yt_channel_id, max_results=self.max_results
        )
        if not videos:
            logger.debug("YouTube: no videos returned from API.")
            return

        last_seen_id = self.state.get("youtube_last_seen_id")

        # Collect videos that are newer than the last-seen one.
        # The API returns results newest-first, so we stop at the first
        # already-seen video.
        new_videos = []
        for video in videos:
            if video["id"] == last_seen_id:
                break
            new_videos.append(video)

        if not new_videos:
            logger.debug("YouTube: no new videos since last check.")
            return

        channel = self.bot.get_channel(self.discord_channel_id)
        if channel is None:
            logger.error(
                "Discord channel ID %s not found – check config.yaml.",
                self.discord_channel_id,
            )
            return

        # Post oldest-first so the channel reads chronologically.
        for video in reversed(new_videos):
            embed = _build_embed(video)
            await channel.send(embed=embed)
            logger.info("Announced YouTube video: %s", video["title"])

        # Persist the most-recent video ID.
        self.state["youtube_last_seen_id"] = videos[0]["id"]
        save_state(self.state)

    @check_youtube.before_loop
    async def before_check_youtube(self) -> None:
        """Wait until the bot is fully connected before the first poll."""
        await self.bot.wait_until_ready()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _build_embed(video: dict) -> discord.Embed:
    """Construct a Discord :class:`discord.Embed` for a YouTube video."""
    embed = discord.Embed(
        title=video["title"],
        url=video["url"],
        description=video["description"] or "*No description available.*",
        color=discord.Color.red(),
    )
    embed.set_author(
        name="GitHub on YouTube",
        url="https://www.youtube.com/@GitHub",
        icon_url="https://www.youtube.com/favicon.ico",
    )
    if video.get("thumbnail"):
        embed.set_image(url=video["thumbnail"])
    if video.get("published"):
        embed.add_field(name="Published", value=video["published"], inline=True)
    embed.set_footer(text="GitHub YouTube Channel • New video!")
    return embed


# Required by discord.py to load the cog.
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YouTubeWatcher(bot))
