"""
bot/cogs/blog_watcher.py – Discord cog that posts a weekly blog digest.

How it works
────────────
1. A background ``discord.ext.tasks`` loop fires once per day at midnight UTC.
2. On each run the cog checks whether today (UTC) is the configured
   ``digest_day`` (default: Thursday).
3. If it is Thursday and a digest hasn't already been sent today, the cog:
     a. Parses the GitHub Blog RSS feed.
     b. Filters entries published in the past 7 days whose title, summary, or
        body contains **any** of the configured ``keywords``.
     c. Takes up to ``digest_count`` matching posts (newest first — RSS feeds
        do not carry view-count data).
     d. Posts a single rich embed digest to the configured Discord channel.
4. The date of the last digest is persisted to ``data/state.json`` so the bot
   does not re-post if it restarts on the same Thursday.

config.yaml keys used (under ``blog:``)
────────────────────────────────────────
  feed_url           – RSS/Atom feed URL (default: https://github.blog/feed/)
  discord_channel_id – Discord channel ID to post the digest in
  digest_day         – Day of week for the digest (default: "thursday")
  keywords           – List of topic keywords to filter posts (OR logic)
  digest_count       – Number of posts in the digest (default: 3)
  search_pool        – Feed entries to inspect before stopping (default: 20)
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone
from typing import List

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.blog_fetcher import BlogFetcher
from utils.state import load_state, save_state

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


class BlogWatcher(commands.Cog):
    """Background task that posts a weekly blog digest on Thursdays."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cfg = bot.config["blog"]

        self.discord_channel_id: int = int(cfg["discord_channel_id"])
        self.keywords: List[str] = cfg.get("keywords", _DEFAULT_KEYWORDS)
        self.digest_count: int = int(cfg.get("digest_count", 3))
        self.search_pool: int = int(cfg.get("search_pool", 20))
        digest_day_value = cfg.get("digest_day", "thursday")
        digest_day_str: str = str(digest_day_value).strip().lower()
        if digest_day_str not in _WEEKDAY_MAP:
            valid_days = ", ".join(_WEEKDAY_MAP.keys())
            raise ValueError(
                f"Invalid blog.digest_day value: {digest_day_value!r}. "
                f"Expected one of: {valid_days}."
            )
        self.digest_weekday: int = _WEEKDAY_MAP[digest_day_str]

        self.blog_client = BlogFetcher(feed_url=cfg["feed_url"])
        self.state: dict = load_state()

        self.weekly_digest.start()

    def cog_unload(self) -> None:
        """Clean up the background task when the cog is unloaded."""
        self.weekly_digest.cancel()

    # ------------------------------------------------------------------
    # Background task – fires once per day, acts only on the digest day
    # ------------------------------------------------------------------

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def weekly_digest(self) -> None:
        """Post the weekly blog digest if today is the configured digest day."""
        try:
            now = datetime.now(tz=timezone.utc)

            if now.weekday() != self.digest_weekday:
                return

            # Avoid double-posting if the bot restarts on the same digest day.
            today_str = now.strftime("%Y-%m-%d")
            if self.state.get("blog_last_digest_date") == today_str:
                logger.debug("Blog digest already sent for %s, skipping.", today_str)
                return

            logger.info(
                "Running weekly blog digest (keywords=%s, date=%s)",
                self.keywords,
                today_str,
            )

            since = now - timedelta(days=7)
            posts = await asyncio.to_thread(
                self.blog_client.get_posts_since_by_keywords,
                since=since,
                keywords=self.keywords,
                max_results=self.digest_count,
                search_pool=self.search_pool,
            )

            try:
                channel = await self.bot.fetch_channel(self.discord_channel_id)
            except discord.NotFound:
                logger.error(
                    "Discord channel ID %s not found – check config.yaml.",
                    self.discord_channel_id,
                )
                return
            except discord.Forbidden:
                logger.error(
                    "Discord channel ID %s is not accessible (missing permissions).",
                    self.discord_channel_id,
                )
                return
            except discord.HTTPException as exc:
                logger.error(
                    "Failed to fetch Discord channel ID %s: %s",
                    self.discord_channel_id,
                    exc,
                )
                return

            if not posts:
                logger.warning(
                    "Blog digest query returned no posts for keywords %s. "
                    "Because an empty result may also indicate a feed fetch error, "
                    "skipping the 'no posts' message and not marking the digest as "
                    "sent. This week's digest will be skipped entirely; the next "
                    "attempt will not occur until next week's scheduled digest day.",
                    self.keywords,
                )
                return

            embed = _build_digest_embed(posts, self.keywords, since, now)
            await channel.send(embed=embed)
            logger.info(
                "Posted blog weekly digest: %d post(s).", len(posts)
            )

            self.state["blog_last_digest_date"] = today_str
            save_state(self.state)
        except Exception:
            logger.exception("Weekly blog digest failed; the next scheduled run will retry.")

    @weekly_digest.before_loop
    async def before_weekly_digest(self) -> None:
        """Wait until the bot is fully connected before the first check."""
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Slash command – manual trigger
    # ------------------------------------------------------------------

    @app_commands.command(
        name="blogdigest",
        description="Manually run the GitHub Blog weekly digest right now.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def blogdigest(self, interaction: discord.Interaction) -> None:
        """Slash command to trigger the blog digest immediately."""
        await interaction.response.defer(ephemeral=True)

        try:
            now = datetime.now(tz=timezone.utc)
            since = now - timedelta(days=7)

            posts = await asyncio.to_thread(
                self.blog_client.get_posts_since_by_keywords,
                since=since,
                keywords=self.keywords,
                max_results=self.digest_count,
                search_pool=self.search_pool,
            )

            try:
                channel = await self.bot.fetch_channel(self.discord_channel_id)
            except discord.NotFound:
                await interaction.followup.send(
                    f"❌ Channel ID `{self.discord_channel_id}` not found — check `config.yaml`.",
                    ephemeral=True,
                )
                return
            except discord.Forbidden:
                await interaction.followup.send(
                    f"❌ Channel ID `{self.discord_channel_id}` is not accessible — check bot permissions.",
                    ephemeral=True,
                )
                return
            except discord.HTTPException as exc:
                await interaction.followup.send(
                    f"❌ Failed to fetch channel: {exc}",
                    ephemeral=True,
                )
                return

            if not posts:
                await interaction.followup.send(
                    "⚠️ No matching blog posts found for the past 7 days.",
                    ephemeral=True,
                )
                return

            embed = _build_digest_embed(posts, self.keywords, since, now)
            await channel.send(embed=embed)
            logger.info("Manual blog digest posted by %s: %d post(s).", interaction.user, len(posts))
            await interaction.followup.send(
                f"✅ Blog digest posted to <#{self.discord_channel_id}> ({len(posts)} post(s)).",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Manual blog digest failed for %s.", interaction.user)
            try:
                await interaction.followup.send(
                    "❌ Failed to run the blog digest. Please try again later and check the bot logs.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                logger.exception(
                    "Failed to send manual blog digest error response to %s.",
                    interaction.user,
                )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

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
    posts: list,
    keywords: List[str],
    since: datetime,
    now: datetime,
) -> discord.Embed:
    """Construct a Discord :class:`discord.Embed` for the weekly blog digest."""
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    topics_str = ", ".join(keywords)
    embed = discord.Embed(
        title="📝 GitHub — Weekly Blog Digest",
        description=(
            f"Recent GitHub Blog posts from the past week ({date_range}).\n"
            f"**Topics:** {topics_str}"
        ),
        color=discord.Color.green(),
    )
    embed.set_author(
        name="GitHub Blog",
        url="https://github.blog",
        icon_url="https://github.githubassets.com/favicons/favicon.png",
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, post in enumerate(posts):
        medal = medals[i] if i < len(medals) else f"#{i + 1}"
        pub = post.get("published", "")
        pub_line = f"Published: {pub}\n" if pub else ""
        field_value = (
            f"[📖 Read on GitHub Blog]({post['url']})\n"
            f"{pub_line}"
            f"{_truncate(post['summary'], 200) or '*No summary.*'}"
        )
        embed.add_field(
            name=f"{medal} {post['title']}",
            value=field_value,
            inline=False,
        )

    embed.set_footer(text="GitHub Blog • Weekly Digest")
    return embed


# Required by discord.py to load the cog.
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlogWatcher(bot))
