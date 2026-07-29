"""One-shot Discord digest runner for scheduled host cron jobs."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from googleapiclient.errors import HttpError

from utils.blog_fetcher import BlogFetcher
from utils.embeds import build_blog_embed, build_youtube_embed
from utils.youtube_api import YouTubeClient

logger = logging.getLogger(__name__)


class DigestRunError(RuntimeError):
    """Raised when one or more digest deliveries fail."""


async def run_digests(
    client: discord.Client,
    config: dict,
    *,
    now: datetime | None = None,
) -> None:
    """Fetch and post both configured digests for one cron invocation."""
    now = now or datetime.now(tz=timezone.utc)
    errors: list[Exception] = []

    try:
        await _run_blog_digest(client, config["blog"], now)
    except (discord.HTTPException, OSError, ValueError) as exc:
        logger.exception("Blog digest failed.")
        errors.append(exc)

    try:
        await _run_youtube_digest(client, config["youtube"], now)
    except (discord.HTTPException, HttpError, OSError, ValueError) as exc:
        logger.exception("YouTube digest failed.")
        errors.append(exc)

    if errors:
        raise DigestRunError(f"{len(errors)} digest(s) failed")


async def _run_blog_digest(
    client: discord.Client,
    config: dict,
    now: datetime,
) -> None:
    since = now - timedelta(days=7)
    fetcher = BlogFetcher(feed_url=config["feed_url"])
    posts = await asyncio.to_thread(
        fetcher.get_posts_since_by_keywords,
        since=since,
        keywords=config.get("keywords", []),
        max_results=int(config.get("digest_count", 3)),
        search_pool=int(config.get("search_pool", 20)),
    )
    if not posts:
        logger.warning("No matching blog posts found for the past 7 days.")
        return

    channel = await client.fetch_channel(int(config["discord_channel_id"]))
    await channel.send(embed=build_blog_embed(posts, config.get("keywords", []), since, now))
    logger.info("Posted blog digest: %d post(s).", len(posts))


async def _run_youtube_digest(
    client: discord.Client,
    config: dict,
    now: datetime,
) -> None:
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = today_midnight - timedelta(days=7)
    youtube = YouTubeClient(api_key=os.environ["YOUTUBE_API_KEY"])
    videos = await asyncio.to_thread(
        youtube.get_top_recent_videos,
        channel_id=config["channel_id"],
        published_after=since,
        top_n=int(config.get("digest_count", 3)),
        search_pool=int(config.get("search_pool", 20)),
    )
    if not videos:
        logger.warning("No YouTube videos found for the past 7 days.")
        return

    channel = await client.fetch_channel(int(config["discord_channel_id"]))
    await channel.send(embed=build_youtube_embed(videos, since, now))
    logger.info("Posted YouTube digest: %d video(s).", len(videos))


async def run_cron_job(config: dict, token: str) -> None:
    """Connect to Discord, execute the digest once, and disconnect."""
    client = discord.Client(intents=discord.Intents.default())
    run_error: Exception | None = None

    @client.event
    async def on_ready() -> None:
        nonlocal run_error
        try:
            await run_digests(client, config)
        except Exception as exc:
            run_error = exc
        finally:
            await client.close()

    await client.start(token)
    if run_error is not None:
        raise run_error
