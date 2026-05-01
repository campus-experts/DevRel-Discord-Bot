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
    from utils.youtube_api import YouTubeClient

    client = YouTubeClient(api_key="YOUR_KEY")
    videos  = client.get_recent_videos("UC7c3Kb6jYCRj4JOHHZTxKsA", max_results=5)
    for v in videos:
        print(v["title"], v["url"])
"""

import logging
from typing import List

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

    def get_recent_videos(
        self, channel_id: str, max_results: int = 5
    ) -> List[dict]:
        """Return a list of the most recent videos from *channel_id*.

        Each returned dict contains:

        - ``id``          – YouTube video ID  (e.g. ``"dQw4w9WgXcQ"``)
        - ``title``       – Video title
        - ``description`` – First 500 characters of the video description
        - ``url``         – Full ``https://www.youtube.com/watch?v=…`` URL
        - ``published``   – ISO 8601 publish timestamp (string)
        - ``thumbnail``   – URL of the high-quality thumbnail image

        Returns an empty list when the API call fails so callers can handle
        the absence of results gracefully.
        """
        try:
            response = (
                self._service.search()
                .list(
                    part="snippet",
                    channelId=channel_id,
                    order="date",
                    type="video",
                    maxResults=max_results,
                )
                .execute()
            )
        except HttpError as exc:
            logger.error("YouTube API error (channel=%s): %s", channel_id, exc)
            return []

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
                }
            )
        return videos
