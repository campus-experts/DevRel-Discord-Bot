"""Fetch the weekly content and post it to Discord."""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml
from dotenv import load_dotenv

from utils.blog_fetcher import BlogFetcher
from utils.embeds import build_blog_embed, build_youtube_embed
from utils.youtube_api import YouTubeClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
CONFIG_PATH = Path("config/config.yaml")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with CONFIG_PATH.open() as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError("Configuration file is empty or malformed")
    return config


def post_to_discord(token: str, channel_id: int, embed: dict) -> None:
    request = Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=json.dumps({"embeds": [embed]}).encode(),
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mona Media",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30):
            return
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Discord API returned HTTP {exc.code}: {detail}") from exc


def run_digest(config: dict, token: str) -> None:
    now = datetime.now(tz=timezone.utc)
    since = now - timedelta(days=7)

    blog = config["blog"]
    posts = BlogFetcher(blog["feed_url"]).get_posts_since_by_keywords(
        since=since,
        keywords=blog["keywords"],
        max_results=int(blog.get("digest_count", 3)),
        search_pool=int(blog.get("search_pool", 20)),
    )
    if posts:
        post_to_discord(
            token,
            int(blog["discord_channel_id"]),
            build_blog_embed(posts, blog["keywords"], since, now),
        )
        logger.info("Posted blog digest with %d post(s).", len(posts))
    else:
        logger.warning("No matching blog posts found.")

    youtube = config["youtube"]
    videos = YouTubeClient(os.environ["YOUTUBE_API_KEY"]).get_top_recent_videos(
        channel_id=youtube["channel_id"],
        published_after=since,
        top_n=int(youtube.get("digest_count", 3)),
        search_pool=int(youtube.get("search_pool", 20)),
    )
    if videos:
        post_to_discord(
            token,
            int(youtube["discord_channel_id"]),
            build_youtube_embed(videos, since, now),
        )
        logger.info("Posted YouTube digest with %d video(s).", len(videos))
    else:
        logger.warning("No YouTube videos found.")


def main() -> None:
    load_dotenv()
    required = ["DISCORD_TOKEN", "YOUTUBE_API_KEY"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    run_digest(load_config(), os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Digest job failed.")
        sys.exit(1)
