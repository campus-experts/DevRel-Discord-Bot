import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from bot.cron_runner import run_digests


class _FakeChannel:
    def __init__(self):
        self.embeds = []

    async def send(self, embed):
        self.embeds.append(embed)


class _FakeClient:
    def __init__(self, channel):
        self.channel = channel
        self.fetch_channel = AsyncMock(return_value=channel)


class CronRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = {
            "blog": {
                "feed_url": "https://github.blog/feed/",
                "discord_channel_id": 123,
                "keywords": ["Security"],
                "digest_count": 1,
                "search_pool": 10,
            },
            "youtube": {
                "channel_id": "UC7c3Kb6jYCRj4JOHHZTxKsQ",
                "discord_channel_id": 456,
                "digest_count": 1,
                "search_pool": 10,
            },
        }
        self.now = datetime(2026, 7, 23, 1, tzinfo=timezone.utc)

    async def test_run_posts_both_digests(self):
        channel = _FakeChannel()
        client = _FakeClient(channel)
        blog = [
            {
                "title": "Security update",
                "summary": "Summary",
                "url": "https://github.blog/post",
                "published": "2026-07-22",
            }
        ]
        videos = [
            {
                "title": "GitHub video",
                "description": "Description",
                "url": "https://youtube.example/video",
                "thumbnail": "",
                "view_count": 100,
            }
        ]

        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake-key"}), patch(
            "bot.cron_runner.BlogFetcher"
        ) as blog_fetcher, patch(
            "bot.cron_runner.YouTubeClient"
        ) as youtube_client, patch(
            "bot.cron_runner.asyncio.to_thread",
            new=AsyncMock(side_effect=[blog, videos]),
        ):
            await run_digests(client, self.config, now=self.now)

        self.assertEqual(len(channel.embeds), 2)
        self.assertEqual(client.fetch_channel.await_count, 2)
        blog_fetcher.assert_called_once_with(feed_url="https://github.blog/feed/")
        youtube_client.assert_called_once_with(api_key="fake-key")

if __name__ == "__main__":
    unittest.main()
