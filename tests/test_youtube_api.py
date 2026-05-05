import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from utils.youtube_api import YouTubeClient


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeSearchResource:
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
    def __init__(self, search_payload=None, videos_payload=None):
        self.search_capture = {}
        self.videos_capture = {}
        self._search_payload = search_payload or {"items": []}
        self._videos_payload = videos_payload or {"items": []}

    def search(self):
        return _FakeSearchResource(self._search_payload, self.search_capture)

    def videos(self):
        return _FakeVideosResource(self._videos_payload, self.videos_capture)


class YouTubeApiTests(unittest.TestCase):
    def test_search_by_keywords_requires_timezone_aware_datetime(self) -> None:
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = _FakeService()
        with self.assertRaises(ValueError):
            client.search_by_keywords(
                channel_id="channel-id",
                keywords=["Copilot"],
                published_after=datetime.now(),
            )

    def test_search_by_keywords_joins_list_keywords_and_maps_response(self) -> None:
        service = _FakeService(
            search_payload={
                "items": [
                    {
                        "id": {"videoId": "abc123"},
                        "snippet": {
                            "title": "Copilot update",
                            "description": "Great release notes",
                            "publishedAt": "2026-05-01T00:00:00Z",
                            "thumbnails": {"high": {"url": "https://img.example/1.jpg"}},
                        },
                    }
                ]
            }
        )
        client = YouTubeClient.__new__(YouTubeClient)
        client._service = service

        videos = client.search_by_keywords(
            channel_id="channel-id",
            keywords=["Copilot", "Security"],
            published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
            max_results=15,
        )

        self.assertEqual(service.search_capture["q"], "Copilot|Security")
        self.assertEqual(service.search_capture["channelId"], "channel-id")
        self.assertEqual(service.search_capture["maxResults"], 15)
        self.assertEqual(videos[0]["id"], "abc123")
        self.assertEqual(videos[0]["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(videos[0]["view_count"], 0)

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

    def test_get_top_videos_by_keywords_sorts_descending_by_view_count(self) -> None:
        client = YouTubeClient.__new__(YouTubeClient)
        with patch.object(
            client,
            "search_by_keywords",
            return_value=[
                {"id": "a", "title": "A", "view_count": 0},
                {"id": "b", "title": "B", "view_count": 0},
                {"id": "c", "title": "C", "view_count": 0},
            ],
        ), patch.object(
            client, "get_video_statistics", return_value={"a": 10, "b": 300, "c": 50}
        ):
            top = client.get_top_videos_by_keywords(
                channel_id="channel-id",
                keywords=["Copilot"],
                published_after=datetime(2026, 5, 1, tzinfo=timezone.utc),
                top_n=2,
                search_pool=20,
            )

        self.assertEqual([video["id"] for video in top], ["b", "c"])
        self.assertEqual([video["view_count"] for video in top], [300, 50])


if __name__ == "__main__":
    unittest.main()
