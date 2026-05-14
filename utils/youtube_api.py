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
        # Cache uploads playlist IDs to avoid a redundant channels.list call
        # on every digest run.
        self._uploads_playlist_cache: dict = {}

    def _get_uploads_playlist_id(self, channel_id: str) -> str:
        """Return the uploads playlist ID for *channel_id*.

        Fetches ``contentDetails.relatedPlaylists.uploads`` from the YouTube
        Data API on first call and caches the result.  Raises
        :class:`ValueError` if the channel is not found.
        """
        if channel_id not in self._uploads_playlist_cache:
            response = (
                self._service.channels()
                .list(part="contentDetails", id=channel_id)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                raise ValueError(
                    f"YouTube channel {channel_id!r} not found. "
                    "Check the channel_id in config.yaml."
                )
            playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            self._uploads_playlist_cache[channel_id] = playlist_id
        return self._uploads_playlist_cache[channel_id]

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_recent(
        self,
        channel_id: str,
        published_after: datetime,
        max_results: int = 20,
    ) -> List[dict]:
        """Return videos uploaded to *channel_id* after *published_after*.

        Uses the channel's **uploads playlist** (``playlistItems.list``) rather
        than ``search.list``.  This is more reliable because:

        - ``search.list`` has unpredictable indexing delays and can silently
          omit recently-uploaded videos and YouTube Shorts.
        - ``playlistItems.list`` reflects the actual upload history immediately.
        - ``playlistItems.list`` costs **1 quota unit** vs 100 for ``search.list``.

        The uploads playlist ID is retrieved via ``channels.list`` and cached
        for the lifetime of the client instance.

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
        Raises :class:`ValueError` if the channel cannot be found.
        """
        if published_after.tzinfo is None:
            raise ValueError(
                "published_after must be a timezone-aware datetime (e.g. use timezone.utc)"
            )

        uploads_playlist_id = self._get_uploads_playlist_id(channel_id)

        response = (
            self._service.playlistItems()
            .list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=max_results,
            )
            .execute()
        )

        videos: List[dict] = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            content_details = item.get("contentDetails", {})

            video_id = snippet.get("resourceId", {}).get("videoId", "")
            if not video_id:
                continue

            # contentDetails.videoPublishedAt is the authoritative publish date.
            # snippet.publishedAt is when the item was added to the playlist
            # (usually identical for the uploads playlist, but videoPublishedAt
            # is preferred).
            published_at_str = content_details.get(
                "videoPublishedAt", snippet.get("publishedAt", "")
            )

            if published_at_str:
                published_at = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )
                # The uploads playlist is ordered newest-first.  Once we reach
                # a video at or before the window boundary, all remaining items
                # will also be out of the window.
                if published_at <= published_after:
                    break

            videos.append(
                {
                    "id": video_id,
                    "title": snippet.get("title", "Untitled"),
                    "description": snippet.get("description", "")[:500],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published": published_at_str,
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
