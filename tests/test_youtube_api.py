import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from googleapiclient.errors import HttpError

from utils.youtube_api import YouTubeClient


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakePlaylistItemsResource:
    def __init__(self, payload, capture):
        self._payload = payload
        self._capture = capture

    def list(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeRequest(self._payload)


class _FakeVideosResource:
    def __init__(self, payload, capture):
        self._payload = payload
        self._capture = capture

    def list(self, **kwargs):
        self._capture.update(kwargs)
        return _FakeRequest(self._payload)


class _FakeService:
    def __init__(self, playlist_payload=None, videos_payload=None):
        self.playlist_capture = {}
        self.videos_capture = {}
        self._playlist_payload = playlist_payload or {"items": []}
        self._videos_payload = videos_payload or {"items": []}

    def playlistItems(self):
        return _FakePlaylistItemsResource(self._playlist_payload, self.playlist_capture)

    def videos(self):
        return _FakeVideosResource(self._videos_payload, self.videos_capture)


def _playlist_item(video_id, title, description, published_at, thumbnail_url=""):
    """Build a fake playlistItems.list response item."""
    return {
        "snippet": {
            "title": title,
            "description": description,
            "publishedAt": published_at,
            "thumbnails": {"high": {"url": thumbnail_url}} if thumbnail_url else {},
            "resourceId": {"videoId": video_id},
        },
        "contentDetails": {
            "videoPublishedAt": published_at,
        },
    }


class YouTubeApiTests(unittest.TestCase):
    def test_search_recent_propagates_http_error(self) -> None:
        """HttpError from the API must propagate so callers can distinguish
        a genuine empty result from an API failure (e.g. quota exceeded)."""
        fake_resp = MagicMock()
        fake_resp.status = 403
        fake_resp.reason = "quotaExceeded"
        error = HttpError(resp=fake_resp, content=b'{"error":{"message":"quotaExceeded"}}')

        class _ErrorPlaylistResource:
            def list(self, **kwargs):
                raise error

        class _ErrorService:
            def playlistItems(self):
                return _ErrorPlaylistResource()

        client = YouTubeClient.__new__(YouTubeClient)
        client._service = _ErrorService()

        with self.assertRaises(HttpError):
            client.search_recent(
                channel_id="UCxxxxxxxxxxxxxxxxxxxxxxxx",
                published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )

    def test_search_recent_requires_timezone_aware_datetime(self) -> None:
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = _FakeService()
        with self.assertRaises(ValueError):
            client.search_recent(
                channel_id="UCxxxxxxxxxxxxxxxxxxxxxxxx",
                published_after=datetime.now(),
            )

    def test_search_recent_requires_uc_channel_id(self) -> None:
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = _FakeService()
        with self.assertRaises(ValueError):
            client.search_recent(
                channel_id="not-a-uc-id",
                published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )

    def test_search_recent_maps_playlist_response(self) -> None:
        service = _FakeService(
            playlist_payload={
                "items": [
                    _playlist_item(
                        "abc123",
                        "Copilot update",
                        "Great release notes",
                        "2026-05-10T00:00:00Z",
                        "https://img.example/1.jpg",
                    )
                ]
            }
        )
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = service

        videos = client.search_recent(
            channel_id="UC7c3Kb6jYCRj4JOHHZTxKsA",
            published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
            max_results=15,
        )

        # Must use the uploads playlist derived from the channel ID, not search.
        self.assertEqual(service.playlist_capture["playlistId"], "UU7c3Kb6jYCRj4JOHHZTxKsA")
        self.assertEqual(service.playlist_capture["maxResults"], 15)
        self.assertNotIn("q", service.playlist_capture)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["id"], "abc123")
        self.assertEqual(videos[0]["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(videos[0]["view_count"], 0)
        self.assertEqual(videos[0]["thumbnail"], "https://img.example/1.jpg")

    def test_search_recent_excludes_videos_at_or_before_window(self) -> None:
        """Videos published at or before published_after must be excluded."""
        service = _FakeService(
            playlist_payload={
                "items": [
                    _playlist_item("new", "New", "", "2026-05-10T00:00:00Z"),
                    # Exactly at the boundary — should be excluded.
                    _playlist_item("boundary", "Boundary", "", "2026-05-07T00:00:00Z"),
                    _playlist_item("old", "Old", "", "2026-05-01T00:00:00Z"),
                ]
            }
        )
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = service

        videos = client.search_recent(
            channel_id="UCxxxxxxxxxxxxxxxxxxxxxxxx",
            published_after=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )

        self.assertEqual([v["id"] for v in videos], ["new"])

    def test_get_video_statistics_parses_view_counts(self) -> None:
        service = _FakeService(
            videos_payload={
                "items": [
                    {"id": "vid1", "statistics": {"viewCount": "12"}},
                    {"id": "vid2", "statistics": {"viewCount": "3000"}},
                ]
            }
        )
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = service

        stats = client.get_video_statistics(["vid1", "vid2"])

        self.assertEqual(stats, {"vid1": 12, "vid2": 3000})
        self.assertEqual(service.videos_capture["id"], "vid1,vid2")

    def test_get_top_recent_videos_sorts_descending_by_view_count(self) -> None:
        client = YouTubeClient.__new__(YouTubeClient)
        with patch.object(
            client,
            "search_recent",
            return_value=[
                {"id": "a", "title": "A", "view_count": 0},
                {"id": "b", "title": "B", "view_count": 0},
                {"id": "c", "title": "C", "view_count": 0},
            ],
        ), patch.object(
            client, "get_video_statistics", return_value={"a": 10, "b": 300, "c": 50}
        ):
            top = client.get_top_recent_videos(
                channel_id="UCxxxxxxxxxxxxxxxxxxxxxxxx",
                published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
                top_n=2,
                search_pool=20,
            )

        self.assertEqual([video["id"] for video in top], ["b", "c"])
        self.assertEqual([video["view_count"] for video in top], [300, 50])


if __name__ == "__main__":
    unittest.main()
