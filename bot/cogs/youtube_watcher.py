"""
bot/cogs/youtube_watcher.py – Discord cog that posts a weekly YouTube digest.

How it works
────────────
1. A background ``discord.ext.tasks`` loop fires once per day.
2. On each run the cog checks whether today (UTC) is the configured
   ``digest_day`` (default: Thursday).
3. If it is Thursday and a digest hasn't already been sent today, the cog:
     a. Searches the GitHub YouTube channel for videos matching any of the
        configured ``keywords`` published in the past 7 days
        (up to ``search_pool`` candidates).
     b. Fetches view counts for all candidates in a single API call.
     c. Sorts by view count and picks the top ``digest_count`` videos.
     d. Posts a single rich embed digest to the configured Discord channel.
4. The date of the last digest is persisted to ``data/state.json`` so the bot
   does not re-post if it restarts on the same Thursday.

Environment variables required
───────────────────────────────
  YOUTUBE_API_KEY  – YouTube Data API v3 key (set in .env or host secrets)

config.yaml keys used (under ``youtube:``)
───────────────────────────────────────────
  channel_id         – YouTube channel ID to watch
  discord_channel_id – Discord channel ID to post the digest in
  digest_day         – Day of week for the digest (default: "thursday")
  keywords           – List of topic keywords to filter videos (OR logic)
  digest_count       – Number of videos in the digest (default: 3)
  search_pool        – Candidate pool size before view-count ranking (default: 20)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

import discord
from discord.ext import commands, tasks

from utils.state import load_state, save_state
from utils.youtube_api import YouTubeClient

logger = logging.getLogger(__name__)

# Day names (lowercase) mapped to Python weekday integers (Monday=0).
_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_DEFAULT_KEYWORDS = [
    "GitHub Copilot",
    "GitHub Copilot CLI",
    "Security",
    "Developer Skills",
    "Company News",
]


class YouTubeWatcher(commands.Cog):
    """Background task that posts a weekly YouTube digest on Thursdays."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cfg = bot.config["youtube"]

        self.yt_channel_id: str = cfg["channel_id"]
        self.discord_channel_id: int = int(cfg["discord_channel_id"])
        self.keywords: List[str] = cfg.get("keywords", _DEFAULT_KEYWORDS)
        self.digest_count: int = int(cfg.get("digest_count", 3))
        self.search_pool: int = int(cfg.get("search_pool", 20))
        digest_day_str: str = str(cfg.get("digest_day", "thursday")).strip().lower()
        if digest_day_str not in _WEEKDAY_MAP:
            valid_days = ", ".join(_WEEKDAY_MAP.keys())
            raise ValueError(
                f"Invalid youtube.digest_day value {digest_day_str!r}. "
                f"Expected one of: {valid_days}."
            )
        self.digest_weekday: int = _WEEKDAY_MAP[digest_day_str]

        api_key = os.environ["YOUTUBE_API_KEY"]
        self.yt_client = YouTubeClient(api_key=api_key)
        self.state: dict = load_state()

        self.weekly_digest.start()

    def cog_unload(self) -> None:
        """Clean up the background task when the cog is unloaded."""
        self.weekly_digest.cancel()

    # ------------------------------------------------------------------
    # Background task – fires once per day, acts only on the digest day
    # ------------------------------------------------------------------

    @tasks.loop(hours=24)
    async def weekly_digest(self) -> None:
        """Post the weekly YouTube digest if today is the configured digest day."""
        try:
            now = datetime.now(tz=timezone.utc)

            if now.weekday() != self.digest_weekday:
                return

            # Avoid double-posting if the bot restarts on the same digest day.
            today_str = now.strftime("%Y-%m-%d")
            if self.state.get("youtube_last_digest_date") == today_str:
                logger.debug("YouTube digest already sent for %s, skipping.", today_str)
                return

            logger.info(
                "Running weekly YouTube digest (keywords=%s, date=%s)",
                self.keywords,
                today_str,
            )

            since = now - timedelta(days=7)
            videos = await asyncio.to_thread(
                self.yt_client.get_top_videos_by_keywords,
                channel_id=self.yt_channel_id,
                keywords=self.keywords,
                published_after=since,
                top_n=self.digest_count,
                search_pool=self.search_pool,
            )

            channel = self.bot.get_channel(self.discord_channel_id)
            if channel is None:
                logger.error(
                    "Discord channel ID %s not found – check config.yaml.",
                    self.discord_channel_id,
                )
                return

            if not videos:
                logger.warning(
                    "YouTube digest query returned no videos for keywords %s. "
                    "Because an empty result may also indicate a YouTube API error, "
                    "skipping the 'no videos' post and not marking the digest as sent "
                    "so it can be retried later.",
                    self.keywords,
                )
                return

            embed = _build_digest_embed(videos, self.keywords, since, now)
            await channel.send(embed=embed)
            logger.info(
                "Posted YouTube weekly digest: %d video(s).", len(videos)
            )

            self.state["youtube_last_digest_date"] = today_str
            save_state(self.state)
        except Exception:
            logger.exception("Weekly YouTube digest failed; the next scheduled run will retry.")

    @weekly_digest.before_loop
    async def before_weekly_digest(self) -> None:
        """Wait until the bot is fully connected before the first check."""
        await self.bot.wait_until_ready()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_views(count: int) -> str:
    """Return a human-friendly view-count string (e.g. ``"1.2M views"``)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K views"
    return f"{count:,} views"


def _truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars* Unicode code points.

    Python ``str`` objects are sequences of Unicode code points, so slicing
    never splits a multi-byte character.  If the text is longer than
    *max_chars* it is trimmed and an ellipsis is appended.
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _build_digest_embed(
    videos: list,
    keywords: List[str],
    since: datetime,
    now: datetime,
) -> discord.Embed:
    """Construct a Discord :class:`discord.Embed` for the weekly video digest."""
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    topics_str = ", ".join(keywords)
    embed = discord.Embed(
        title="📺 GitHub — Weekly Video Digest",
        description=(
            f"Top GitHub YouTube videos from the past week ({date_range}), "
            f"ranked by views.\n**Topics:** {topics_str}"
        ),
        color=discord.Color.red(),
    )
    embed.set_author(
        name="GitHub on YouTube",
        url="https://www.youtube.com/@GitHub",
        icon_url="https://www.youtube.com/favicon.ico",
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, video in enumerate(videos):
        medal = medals[i] if i < len(medals) else f"#{i + 1}"
        views_str = _fmt_views(video.get("view_count", 0))
        field_value = (
            f"[▶ Watch on YouTube]({video['url']}) • {views_str}\n"
            f"{_truncate(video['description'], 200) or '*No description.*'}"
        )
        embed.add_field(
            name=f"{medal} {video['title']}",
            value=field_value,
            inline=False,
        )
        # Use the thumbnail from the most-viewed video.
        if i == 0 and video.get("thumbnail"):
            embed.set_image(url=video["thumbnail"])

    embed.set_footer(text="GitHub YouTube Channel • Weekly Digest")
    return embed


# Required by discord.py to load the cog.
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(YouTubeWatcher(bot))
