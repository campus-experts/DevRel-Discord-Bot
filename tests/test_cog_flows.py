import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from bot.cogs.blog_watcher import BlogWatcher
from bot.cogs.youtube_watcher import YouTubeWatcher


def _today_name_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%A").lower()


async def _run_inline(func, *args, **kwargs):
    return func(*args, **kwargs)


class _FakeChannel:
    def __init__(self):
        self.embeds = []

    async def send(self, embed):
        self.embeds.append(embed)


class _FakeYouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_top_videos_by_keywords(self, **kwargs):
        return [
            {
                "id": "vid-1",
                "title": "Copilot video",
                "description": "Video summary",
                "url": "https://youtube.example/vid-1",
                "thumbnail": "https://img.example/1.jpg",
                "view_count": 1500,
            }
        ]


class _FakeBlogFetcher:
    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    def get_posts_since_by_keywords(self, **kwargs):
        return [
            {
                "id": "post-1",
                "title": "Security update",
                "summary": "Summary text",
                "url": "https://github.blog/post-1",
                "published": "2026-05-01",
            }
        ]


class _FakeBot:
    def __init__(self, config, channel):
        self.config = config
        self._channel = channel
        self.fetch_channel = AsyncMock(return_value=channel)

    async def wait_until_ready(self):
        return None


class CogFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_youtube_weekly_digest_fetches_channel_and_posts(self) -> None:
        channel = _FakeChannel()
        bot = _FakeBot(
            config={
                "youtube": {
                    "channel_id": "UC7c3Kb6jYCRj4JOHHZTxKsA",
                    "discord_channel_id": 123456789012345678,
                    "keywords": ["GitHub Copilot"],
                    "digest_count": 1,
                    "search_pool": 10,
                    "digest_day": _today_name_utc(),
                }
            },
            channel=channel,
        )

        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake-key"}, clear=False), patch(
            "discord.ext.tasks.Loop.start", return_value=None
        ), patch(
            "bot.cogs.youtube_watcher.YouTubeClient", _FakeYouTubeClient
        ), patch(
            "bot.cogs.youtube_watcher.load_state", return_value={}
        ), patch(
            "bot.cogs.youtube_watcher.save_state"
        ) as save_state_mock, patch(
            "bot.cogs.youtube_watcher.asyncio.to_thread", side_effect=_run_inline
        ):
            cog = YouTubeWatcher(bot)
            await cog.weekly_digest.coro(cog)

        bot.fetch_channel.assert_awaited_once_with(123456789012345678)
        self.assertEqual(len(channel.embeds), 1)
        saved_state = save_state_mock.call_args.args[0]
        self.assertIn("youtube_last_digest_date", saved_state)

    async def test_blog_weekly_digest_fetches_channel_and_posts(self) -> None:
        channel = _FakeChannel()
        bot = _FakeBot(
            config={
                "blog": {
                    "feed_url": "https://github.blog/feed/",
                    "discord_channel_id": 123456789012345679,
                    "keywords": ["Security"],
                    "digest_count": 1,
                    "search_pool": 10,
                    "digest_day": _today_name_utc(),
                }
            },
            channel=channel,
        )

        with patch("discord.ext.tasks.Loop.start", return_value=None), patch(
            "bot.cogs.blog_watcher.BlogFetcher", _FakeBlogFetcher
        ), patch(
            "bot.cogs.blog_watcher.load_state", return_value={}
        ), patch(
            "bot.cogs.blog_watcher.save_state"
        ) as save_state_mock, patch(
            "bot.cogs.blog_watcher.asyncio.to_thread", side_effect=_run_inline
        ):
            cog = BlogWatcher(bot)
            await cog.weekly_digest.coro(cog)

        bot.fetch_channel.assert_awaited_once_with(123456789012345679)
        self.assertEqual(len(channel.embeds), 1)
        saved_state = save_state_mock.call_args.args[0]
        self.assertIn("blog_last_digest_date", saved_state)


if __name__ == "__main__":
    unittest.main()
