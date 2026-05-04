"""
utils/blog_fetcher.py – GitHub Blog RSS feed fetcher.

Uses the ``feedparser`` library to parse any RSS / Atom feed and return
a normalised list of recent posts.  Defaults to the GitHub Blog feed.

GitHub Blog RSS feed URL: https://github.blog/feed/

Usage example
─────────────
    from datetime import datetime, timezone, timedelta
    from utils.blog_fetcher import BlogFetcher

    fetcher  = BlogFetcher()                        # uses GitHub Blog
    since    = datetime.now(tz=timezone.utc) - timedelta(days=7)
    keywords = ["GitHub Copilot", "GitHub Copilot CLI", "Security",
                "Developer Skills", "Company News"]
    posts    = fetcher.get_posts_since_by_keywords(since=since, keywords=keywords, max_results=3)
    for post in posts:
        print(post["title"], post["url"])
"""

import logging
import re
from datetime import datetime, timezone
from typing import List, Union

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

    def get_posts_since_by_keywords(
        self,
        since: datetime,
        keywords: Union[str, List[str]],
        max_results: int = 3,
        search_pool: int = 20,
    ) -> List[dict]:
        """Return up to *max_results* posts published after *since* that mention any of *keywords*.

        *keywords* may be a single string or a list of strings.  A post matches
        if **any** keyword (case-insensitive) appears in its title, summary, or
        body content.  Up to *search_pool* feed entries are inspected.

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
        if since.tzinfo is None:
            raise ValueError(
                "since must be a timezone-aware datetime (e.g. use timezone.utc)"
            )

        feed = feedparser.parse(self.feed_url)

        if feed.bozo:
            logger.warning(
                "Feed parse warning for %s: %s",
                self.feed_url,
                feed.bozo_exception,
            )
            # bozo doesn't always mean the feed is unusable – continue.

        # Normalise keywords to a lowercase list for uniform matching.
        if isinstance(keywords, str):
            keywords_lower = [keywords.lower()]
        else:
            keywords_lower = [k.lower() for k in keywords]

        matching: List[dict] = []

        for entry in feed.entries[:search_pool]:
            # ── Date filter ────────────────────────────────────────────────
            published_parsed = getattr(entry, "published_parsed", None)
            updated_parsed = getattr(entry, "updated_parsed", None)
            parsed_date = published_parsed or updated_parsed

            if parsed_date is None:
                # "since" queries must exclude entries whose publish/update
                # time cannot be determined.
                continue

            try:
                # feedparser gives a time.struct_time in UTC; construct a
                # timezone-aware datetime directly from the first 6 fields.
                pub_dt = datetime(*parsed_date[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping feed entry with invalid parsed date from %s: %r",
                    self.feed_url,
                    entry.get("link", entry.get("id", "")),
                )
                continue

            if pub_dt < since:
                # Feeds are not guaranteed to be strictly newest-first,
                # so skip this old entry and continue scanning.
                continue

            # ── Keyword filter (OR logic) ───────────────────────────────────
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            # Some feeds expose full content separately.
            content_blocks = entry.get("content", [])
            content = content_blocks[0].get("value", "") if content_blocks else ""

            searchable_text = f"{title} {summary} {content}".lower()
            if not any(kw in searchable_text for kw in keywords_lower):
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
