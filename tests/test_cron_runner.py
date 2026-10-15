import io
import json
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from main import post_to_discord, run_digest


class CronRunnerTests(unittest.TestCase):
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
        self.posts = [{"title": "Security", "summary": "Summary", "url": "https://example.com", "published": "today"}]
        self.videos = [{"title": "Video", "description": "Description", "url": "https://youtube.com/watch?v=1", "thumbnail": "", "view_count": 1}]
        environment = patch.dict(os.environ, {"YOUTUBE_API_KEY": "fake-key"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_run_digest_fetches_and_posts_blog_and_youtube(self):
        with patch(
            "main.BlogFetcher.get_posts_since_by_keywords", return_value=self.posts
        ), patch(
            "main.YouTubeClient.get_top_recent_videos", return_value=self.videos
        ), patch("main.post_to_discord") as post:
            run_digest(self.config, "discord-token")

        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].args[0], "discord-token")
        self.assertEqual(post.call_args_list[0].args[1], 123)
        self.assertIsNone(post.call_args_list[0].kwargs["mention_role_id"])
        self.assertEqual(post.call_args_list[1].args[1], 456)

    def test_run_digest_tags_only_blog_and_preserves_embeds(self):
        for role_id in ("123456789012345678", 123456789012345678, None, ""):
            with self.subTest(role_id=role_id):
                self.config["blog"]["mention_role_id"] = role_id
                with patch(
                    "main.BlogFetcher.get_posts_since_by_keywords", return_value=self.posts
                ), patch(
                    "main.YouTubeClient.get_top_recent_videos", return_value=self.videos
                ), patch("main.urlopen") as send:
                    run_digest(self.config, "discord-token")

                self.assertEqual(send.call_count, 2)
                blog_payload, youtube_payload = [
                    json.loads(call.args[0].data) for call in send.call_args_list
                ]
                self.assertEqual(len(blog_payload["embeds"][0]["fields"]), 1)
                self.assertEqual(len(youtube_payload["embeds"][0]["fields"]), 1)
                if role_id:
                    self.assertEqual(blog_payload["content"], "<@&123456789012345678>")
                    self.assertEqual(
                        blog_payload["allowed_mentions"],
                        {"parse": [], "roles": ["123456789012345678"]},
                    )
                else:
                    self.assertNotIn("content", blog_payload)
                    self.assertEqual(blog_payload["allowed_mentions"], {"parse": []})
                self.assertNotIn("content", youtube_payload)
                self.assertEqual(youtube_payload["allowed_mentions"], {"parse": []})

    def test_invalid_role_id_fails_before_fetching_or_posting(self):
        for role_id in ("Campus Expert", "<@&123>", "0", -1, True, 1.5, [], {}, "１２３", 2**64):
            with self.subTest(role_id=role_id):
                self.config["blog"]["mention_role_id"] = role_id
                with patch(
                    "main.BlogFetcher.get_posts_since_by_keywords"
                ) as blog, patch(
                    "main.YouTubeClient.get_top_recent_videos"
                ) as youtube, patch("main.urlopen") as send:
                    with self.assertRaisesRegex(ValueError, "blog.mention_role_id"):
                        run_digest(self.config, "discord-token")
                blog.assert_not_called()
                youtube.assert_not_called()
                send.assert_not_called()

    def test_empty_blog_does_not_tag_youtube(self):
        self.config["blog"]["mention_role_id"] = "123456789012345678"
        with patch(
            "main.BlogFetcher.get_posts_since_by_keywords", return_value=[]
        ), patch(
            "main.YouTubeClient.get_top_recent_videos", return_value=self.videos
        ), patch("main.urlopen") as send:
            run_digest(self.config, "discord-token")

        send.assert_called_once()
        request = send.call_args.args[0]
        self.assertIn("/channels/456/messages", request.full_url)
        payload = json.loads(request.data)
        self.assertNotIn("content", payload)
        self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_discord_http_errors_are_reported(self):
        error = HTTPError(
            "https://discord.com/api/v10/channels/123/messages",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"message": "Missing Permissions"}'),
        )
        with patch("main.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403.*Missing Permissions"):
                post_to_discord("discord-token", 123, {}, "123456789012345678")


if __name__ == "__main__":
    unittest.main()
