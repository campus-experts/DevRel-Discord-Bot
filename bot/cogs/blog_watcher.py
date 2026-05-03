"""
bot/cogs/blog_watcher.py – Discord cog that posts a weekly Copilot blog digest.

How it works
────────────
1. A background ``discord.ext.tasks`` loop fires every hour.
2. Inside the loop the cog checks whether the current UTC day and hour match
   the configured ``digest_day`` / ``digest_hour`` (default: Thursday 20:00 UTC).
3. If it is the right time and a digest hasn't already been sent today, the cog:
     a. Parses the GitHub Blog RSS feed.
     b. Filters entries published in the past 7 days whose title, summary, or
        body contains ``keyword`` (default: "Copilot").
     c. Takes up to ``digest_count`` matching posts (newest first — RSS feeds
        do not carry view-count data).
     d. Posts a single rich embed digest to the configured Discord channel.
4. The date of the last digest is persisted to ``data/state.json`` so the bot
   does not re-post if it restarts on the same day.

config.yaml keys used (under ``blog:``)
────────────────────────────────────────
  feed_url           – RSS/Atom feed URL (default: https://github.blog/feed/)
  discord_channel_id – Discord channel ID to post the digest in
  digest_day         – Day of week for the digest (default: "thursday")
  digest_hour        – UTC hour for the digest (default: 20)
  keyword            – Keyword filter for post search (default: "Copilot")
  digest_count       – Number of posts in the digest (default: 3)
  search_pool        – Feed entries to inspect before stopping (default: 20)
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from utils.blog_fetcher import BlogFetcher
from utils.state import load_state, save_state

logger = logging.getLogger(__name__)

# Day names (lowercase) mapped to Python weekday integers (Monday=0).
_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


class BlogWatcher(commands.Cog):
    """Background task that posts a weekly Copilot blog digest."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cfg = bot.config["blog"]

        self.discord_channel_id: int = int(cfg["discord_channel_id"])
        self.keyword: str = cfg.get("keyword", "Copilot")
        self.digest_count: int = int(cfg.get("digest_count", 3))
        self.search_pool: int = int(cfg.get("search_pool", 20))
        self.digest_hour: int = int(cfg.get("digest_hour", 20))
        digest_day_str: str = cfg.get("digest_day", "thursday").lower()
        self.digest_weekday: int = _WEEKDAY_MAP.get(digest_day_str, 3)  # default Thursday

        self.blog_client = BlogFetcher(feed_url=cfg["feed_url"])
        self.state: dict = load_state()

        self.weekly_digest.start()

    def cog_unload(self) -> None:
        """Clean up the background task when the cog is unloaded."""
        self.weekly_digest.cancel()

    # ------------------------------------------------------------------
    # Background task – fires every hour, acts only on the digest day/hour
    # ------------------------------------------------------------------

    @tasks.loop(hours=1)
    async def weekly_digest(self) -> None:
        """Post the weekly Copilot blog digest if it is the right time."""
        now = datetime.now(tz=timezone.utc)

        if now.weekday() != self.digest_weekday:
            return
        if now.hour != self.digest_hour:
            return

        # Avoid double-posting if the bot restarts within the same digest hour.
        today_str = now.strftime("%Y-%m-%d")
        if self.state.get("blog_last_digest_date") == today_str:
            logger.debug("Blog digest already sent for %s, skipping.", today_str)
            return

        logger.info(
            "Running weekly blog digest (keyword=%s, date=%s)",
            self.keyword,
            today_str,
        )

        since = now - timedelta(days=7)
        posts = self.blog_client.get_posts_since_by_keyword(
            since=since,
            keyword=self.keyword,
            max_results=self.digest_count,
            search_pool=self.search_pool,
        )

        channel = self.bot.get_channel(self.discord_channel_id)
        if channel is None:
            logger.error(
                "Discord channel ID %s not found – check config.yaml.",
                self.discord_channel_id,
            )
            return

        if not posts:
            logger.info(
                "No '%s' blog posts found in the past week.",
                self.keyword,
            )
            await channel.send(
                f"📝 No **{self.keyword}** posts were published on the "
                f"GitHub Blog this week."
            )
        else:
            embed = _build_digest_embed(posts, self.keyword, since, now)
            await channel.send(embed=embed)
            logger.info(
                "Posted blog weekly digest: %d post(s).", len(posts)
            )

        self.state["blog_last_digest_date"] = today_str
        save_state(self.state)

    @weekly_digest.before_loop
    async def before_weekly_digest(self) -> None:
        """Wait until the bot is fully connected before the first check."""
        await self.bot.wait_until_ready()


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
    keyword: str,
    since: datetime,
    now: datetime,
) -> discord.Embed:
    """Construct a Discord :class:`discord.Embed` for the weekly blog digest."""
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    embed = discord.Embed(
        title=f"📝 GitHub {keyword} — Weekly Blog Digest",
        description=(
            f"Recent GitHub Blog posts about **{keyword}** "
            f"from the past week ({date_range})."
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
