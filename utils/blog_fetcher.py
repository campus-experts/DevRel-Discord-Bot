"""
utils/blog_fetcher.py – GitHub Blog RSS feed fetcher.

Uses the ``feedparser`` library to parse any RSS / Atom feed and return
a normalised list of recent posts.  Defaults to the GitHub Blog feed.

GitHub Blog RSS feed URL: https://github.blog/feed/

Usage example
─────────────
    from utils.blog_fetcher import BlogFetcher

    fetcher = BlogFetcher()                        # uses GitHub Blog
    posts   = fetcher.get_recent_posts(max_results=5)
    for post in posts:
        print(post["title"], post["url"])
"""

import logging
import re
from typing import List

import feedparser

logger = logging.getLogger(__name__)

GITHUB_BLOG_FEED_URL = "https://github.blog/feed/"

# Maximum characters of summary to include in a Discord embed.
_SUMMARY_MAX_CHARS = 500


class BlogFetcher:
    """Fetches entries from an RSS/Atom feed (defaults to the GitHub Blog).

    Args:
        feed_url: The URL of the RSS or Atom feed to parse.
    """

    def __init__(self, feed_url: str = GITHUB_BLOG_FEED_URL) -> None:
        self.feed_url = feed_url

    def get_recent_posts(self, max_results: int = 5) -> List[dict]:
        """Return a list of the most recent posts from the configured feed.

        Each returned dict contains:

        - ``id``        – Unique entry identifier (usually the canonical URL)
        - ``title``     – Post title
        - ``summary``   – Plain-text summary (HTML tags stripped, ≤500 chars)
        - ``url``       – Post link
        - ``published`` – Published-date string as found in the feed

        Returns an empty list when the feed cannot be fetched or parsed.
        """
        feed = feedparser.parse(self.feed_url)

        if feed.bozo:
            # ``bozo`` is set by feedparser when the feed is not well-formed.
            logger.warning(
                "Feed parse warning for %s: %s",
                self.feed_url,
                feed.bozo_exception,
            )
            # bozo doesn't always mean the feed is unusable – continue.

        posts: List[dict] = []
        for entry in feed.entries[:max_results]:
            raw_summary = entry.get("summary", "")
            clean_summary = _strip_html(raw_summary)[:_SUMMARY_MAX_CHARS]

            posts.append(
                {
                    # Fall back to the link if no explicit id is present.
                    "id": entry.get("id", entry.get("link", "")),
                    "title": entry.get("title", "Untitled"),
                    "summary": clean_summary.strip(),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                }
            )
        return posts


def _strip_html(text: str) -> str:
    """Remove HTML tags from *text* and collapse whitespace."""
    no_tags = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple spaces / newlines produced by tag removal
    return re.sub(r"\s+", " ", no_tags)
