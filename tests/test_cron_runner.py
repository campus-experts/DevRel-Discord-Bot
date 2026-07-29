import os
import unittest
from unittest.mock import patch

from main import run_digest


class CronRunnerTests(unittest.TestCase):
    def test_run_digest_fetches_and_posts_blog_and_youtube(self):
        config = {
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
        posts = [{"title": "Security", "summary": "Summary", "url": "https://example.com", "published": "today"}]
        videos = [{"title": "Video", "description": "Description", "url": "https://youtube.com/watch?v=1", "thumbnail": "", "view_count": 1}]

        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake-key"}), patch(
            "main.BlogFetcher.get_posts_since_by_keywords", return_value=posts
        ), patch(
            "main.YouTubeClient.get_top_recent_videos", return_value=videos
        ), patch("main.post_to_discord") as post:
            run_digest(config, "discord-token")

        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].args[0], "discord-token")
        self.assertEqual(post.call_args_list[0].args[1], 123)
        self.assertEqual(post.call_args_list[1].args[1], 456)


if __name__ == "__main__":
    unittest.main()
