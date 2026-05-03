"""
utils/blog_fetcher.py – GitHub Blog RSS feed fetcher.

Uses the ``feedparser`` library to parse any RSS / Atom feed and return
a normalised list of recent posts.  Defaults to the GitHub Blog feed.

GitHub Blog RSS feed URL: https://github.blog/feed/

Usage example
─────────────
    from datetime import datetime, timezone, timedelta
    from utils.blog_fetcher import BlogFetcher

    fetcher = BlogFetcher()                        # uses GitHub Blog
    since   = datetime.now(tz=timezone.utc) - timedelta(days=7)
    posts   = fetcher.get_posts_since_by_keyword(since=since, keyword="Copilot", max_results=3)
    for post in posts:
        print(post["title"], post["url"])
"""

import logging
import re
from datetime import datetime, timezone
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

    def get_posts_since_by_keyword(
        self,
        since: datetime,
        keyword: str,
        max_results: int = 3,
        search_pool: int = 20,
    ) -> List[dict]:
        """Return up to *max_results* posts published after *since* that mention *keyword*.

        Posts are searched by checking whether *keyword* (case-insensitive)
        appears in the title, summary, or body of each entry.  Up to
        *search_pool* feed entries are inspected before stopping.

        Note: RSS feeds do not carry view-count data, so results are ordered
        by publication date (newest first) rather than by engagement.

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
            logger.warning(
                "Feed parse warning for %s: %s",
                self.feed_url,
                feed.bozo_exception,
            )
            # bozo doesn't always mean the feed is unusable – continue.

        keyword_lower = keyword.lower()
        matching: List[dict] = []

        for entry in feed.entries[:search_pool]:
            # ── Date filter ────────────────────────────────────────────────
            published_parsed = getattr(entry, "published_parsed", None)
            if published_parsed is not None:
                # feedparser gives a time.struct_time in UTC; construct a
                # timezone-aware datetime directly from the first 6 fields.
                pub_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if pub_dt < since:
                    # Feeds are newest-first; once we go past the cutoff we
                    # can stop searching.
                    break

            # ── Keyword filter ─────────────────────────────────────────────
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            # Some feeds expose full content separately.
            content_blocks = entry.get("content", [])
            content = content_blocks[0].get("value", "") if content_blocks else ""

            searchable_text = f"{title} {summary} {content}".lower()
            if keyword_lower not in searchable_text:
                continue

            # ── Build post dict ────────────────────────────────────────────
            raw_summary = summary or content
            clean_summary = _strip_html(raw_summary)[:_SUMMARY_MAX_CHARS]

            matching.append(
                {
                    "id": entry.get("id", entry.get("link", "")),
                    "title": title,
                    "summary": clean_summary.strip(),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                }
            )

            if len(matching) >= max_results:
                break

        return matching


def _strip_html(text: str) -> str:
    """Remove HTML tags from *text* and collapse whitespace."""
    no_tags = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple spaces / newlines produced by tag removal
    return re.sub(r"\s+", " ", no_tags)
