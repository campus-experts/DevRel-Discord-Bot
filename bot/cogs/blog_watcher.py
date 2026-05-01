"""
bot/cogs/blog_watcher.py – Discord cog that watches the GitHub Blog RSS feed.

How it works
────────────
1. On startup the cog loads the last-seen post ID from ``data/state.json``
   (created automatically; ignored by .gitignore).
2. A background ``discord.ext.tasks`` loop polls the GitHub Blog RSS feed
   every ``check_interval_minutes`` minutes (configured in config.yaml).
3. Any post whose ID hasn't been seen before is posted to the configured
   Discord channel as a rich embed that includes:
     - Post title (linked to the blog article)
     - Plain-text summary (HTML stripped, ≤500 characters)
     - Publish date
4. The newest post ID is saved to state.json so the bot does not
   re-announce the same post after a restart.

config.yaml keys used (under ``blog:``)
────────────────────────────────────────
  feed_url                – RSS/Atom feed URL (default: https://github.blog/feed/)
  discord_channel_id      – Discord channel ID to post announcements in
  check_interval_minutes  – Poll interval (default: 60)
  max_results             – Posts per feed parse (default: 5)
"""

import logging

import discord
from discord.ext import commands, tasks

from utils.blog_fetcher import BlogFetcher
from utils.state import load_state, save_state

logger = logging.getLogger(__name__)


class BlogWatcher(commands.Cog):
    """Background task that announces new GitHub Blog posts."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cfg = bot.config["blog"]

        self.discord_channel_id: int = int(cfg["discord_channel_id"])
        self.max_results: int = cfg.get("max_results", 5)
        interval: int = cfg.get("check_interval_minutes", 60)

        self.blog_client = BlogFetcher(feed_url=cfg["feed_url"])
        self.state: dict = load_state()

        self.check_blog.change_interval(minutes=interval)
        self.check_blog.start()

    def cog_unload(self) -> None:
        """Clean up the background task when the cog is unloaded."""
        self.check_blog.cancel()

    # ------------------------------------------------------------------
    # Background task
    # ------------------------------------------------------------------

    @tasks.loop(minutes=60)  # default; overridden in __init__ via change_interval
    async def check_blog(self) -> None:
        """Poll the GitHub Blog feed and post announcements for new entries."""
        logger.info("Polling GitHub Blog feed: %s", self.blog_client.feed_url)

        posts = self.blog_client.get_recent_posts(max_results=self.max_results)
        if not posts:
            logger.debug("Blog: no posts returned from feed.")
            return

        last_seen_id = self.state.get("blog_last_seen_id")

        # Collect posts that are newer than the last-seen one.
        new_posts = []
        for post in posts:
            if post["id"] == last_seen_id:
                break
            new_posts.append(post)

        if not new_posts:
            logger.debug("Blog: no new posts since last check.")
            return

        channel = self.bot.get_channel(self.discord_channel_id)
        if channel is None:
            logger.error(
                "Discord channel ID %s not found – check config.yaml.",
                self.discord_channel_id,
            )
            return

        # Post oldest-first so the channel reads chronologically.
        for post in reversed(new_posts):
            embed = _build_embed(post)
            await channel.send(embed=embed)
            logger.info("Announced blog post: %s", post["title"])

        # Persist the most-recent post ID.
        self.state["blog_last_seen_id"] = posts[0]["id"]
        save_state(self.state)

    @check_blog.before_loop
    async def before_check_blog(self) -> None:
        """Wait until the bot is fully connected before the first poll."""
        await self.bot.wait_until_ready()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _build_embed(post: dict) -> discord.Embed:
    """Construct a Discord :class:`discord.Embed` for a blog post."""
    embed = discord.Embed(
        title=post["title"],
        url=post["url"],
        description=post["summary"] or "*No summary available.*",
        color=discord.Color.green(),
    )
    embed.set_author(
        name="GitHub Blog",
        url="https://github.blog",
        icon_url="https://github.githubassets.com/favicons/favicon.png",
    )
    if post.get("published"):
        embed.add_field(name="Published", value=post["published"], inline=True)
    embed.set_footer(text="GitHub Blog • New post!")
    return embed


# Required by discord.py to load the cog.
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BlogWatcher(bot))
