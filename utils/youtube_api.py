"""
utils/youtube_api.py – Thin wrapper around the YouTube Data API v3.

Prerequisites
─────────────
1. Enable the "YouTube Data API v3" in your Google Cloud project:
   https://console.cloud.google.com/apis/library/youtube.googleapis.com

2. Create an API key (Credentials > Create credentials > API key).
   Restrict the key to the YouTube Data API v3 for extra security.

3. Set the key as the ``YOUTUBE_API_KEY`` environment variable (or in .env).

Usage example
─────────────
    from datetime import datetime, timezone, timedelta
    from utils.youtube_api import YouTubeClient

    client = YouTubeClient(api_key="YOUR_KEY")

    # Weekly digest: top 3 videos from the past 7 days (no keyword filter)
    since  = datetime.now(tz=timezone.utc) - timedelta(days=7)
    videos = client.get_top_recent_videos(
        channel_id="UC7c3Kb6jYCRj4JOHHZTxKsA",
        published_after=since,
        top_n=3,
    )
    for v in videos:
        print(v["title"], v["view_count"], v["url"])
"""

import logging
from datetime import datetime
from typing import Dict, List

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeClient:
    """Thin wrapper around the YouTube Data API v3.

    Args:
        api_key: A Google Cloud API key with the YouTube Data API v3 enabled.
    """

    def __init__(self, api_key: str) -> None:
        # ``build`` is called with ``cache_discovery=False`` to avoid
        # writing to the filesystem and to play nicely with read-only hosts.
        self._service = build(
            "youtube",
            "v3",
            developerKey=api_key,
            cache_discovery=False,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_recent(
        self,
        channel_id: str,
        published_after: datetime,
        max_results: int = 20,
    ) -> List[dict]:
        """Search *channel_id* for all videos published after *published_after*.

        Each returned dict contains:

        - ``id``          – YouTube video ID
        - ``title``       – Video title
        - ``description`` – First 500 characters of the video description
        - ``url``         – Full ``https://www.youtube.com/watch?v=…`` URL
        - ``published``   – ISO 8601 publish timestamp (string)
        - ``thumbnail``   – URL of the high-quality thumbnail image
        - ``view_count``  – 0 (placeholder; populate with :meth:`get_video_statistics`)

        Raises :class:`googleapiclient.errors.HttpError` if the API call fails
        so callers can distinguish a genuine empty result from an API error.
        """
        if published_after.tzinfo is None:
            raise ValueError(
                "published_after must be a timezone-aware datetime (e.g. use timezone.utc)"
            )

        published_after_str = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = (
            self._service.search()
            .list(
                part="snippet",
                channelId=channel_id,
                order="date",
                type="video",
                publishedAfter=published_after_str,
                maxResults=max_results,
            )
            .execute()
        )

        videos: List[dict] = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            video_id = item["id"]["videoId"]
            videos.append(
                {
                    "id": video_id,
                    "title": snippet.get("title", "Untitled"),
                    "description": snippet.get("description", "")[:500],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published": snippet.get("publishedAt", ""),
                    "thumbnail": (
                        snippet.get("thumbnails", {})
                        .get("high", {})
                        .get("url", "")
                    ),
                    "view_count": 0,
                }
            )
        return videos

    def get_video_statistics(self, video_ids: List[str]) -> Dict[str, int]:
        """Return a ``{video_id: view_count}`` mapping for the given IDs.

        Uses a single ``videos.list`` call (cheap: 1 quota unit) to batch
        fetch statistics for all supplied IDs at once.

        Returns an empty dict when the API call fails.
        """
        if not video_ids:
            return {}
        try:
            response = (
                self._service.videos()
                .list(
                    part="statistics",
                    id=",".join(video_ids),
                )
                .execute()
            )
        except HttpError as exc:
            logger.error("YouTube API statistics error: %s", exc)
            return {}

        stats: Dict[str, int] = {}
        for item in response.get("items", []):
            vid_id = item["id"]
            raw = item.get("statistics", {}).get("viewCount", "0")
            stats[vid_id] = int(raw)
        return stats

    def get_top_recent_videos(
        self,
        channel_id: str,
        published_after: datetime,
        top_n: int = 3,
        search_pool: int = 20,
    ) -> List[dict]:
        """Return the top *top_n* recent videos from *channel_id* ranked by view count.

        1. Fetches up to *search_pool* videos from *channel_id* published after
           *published_after* (no keyword filter).
        2. Fetches view counts for all candidates in a single batch call.
        3. Sorts by view count descending and returns the top *top_n*.

        Each returned dict contains the same fields as :meth:`search_recent`
        plus a populated ``view_count`` integer.
        """
        videos = self.search_recent(
            channel_id, published_after, max_results=search_pool
        )
        if not videos:
            return []

        stats = self.get_video_statistics([v["id"] for v in videos])
        for video in videos:
            video["view_count"] = stats.get(video["id"], 0)

        videos.sort(key=lambda v: v["view_count"], reverse=True)
        return videos[:top_n]
