import unittest
from datetime import datetime, timezone

from utils.embeds import (
    _fmt_views,
    _truncate,
    build_blog_embed,
    build_youtube_embed,
)


class DigestHelperTests(unittest.TestCase):
    def test_fmt_views_formats_small_and_large_numbers(self) -> None:
        self.assertEqual(_fmt_views(999), "999 views")
        self.assertEqual(_fmt_views(2_200), "2.2K views")
        self.assertEqual(_fmt_views(1_500_000), "1.5M views")

    def test_truncate_helpers_append_ellipsis_when_needed(self) -> None:
        self.assertEqual(_truncate("abcdef", 4), "abc…")

    def test_build_youtube_embed_contains_expected_fields(self) -> None:
        now = datetime.now(tz=timezone.utc)
        embed = build_youtube_embed(
            videos=[
                {
                    "title": "Copilot in Action",
                    "description": "Learn how to use Copilot effectively.",
                    "url": "https://youtube.example/video",
                    "thumbnail": "https://img.example/thumb.jpg",
                    "view_count": 1200,
                }
            ],
            since=now,
            now=now,
        )

        self.assertEqual(embed["title"], "📺 GitHub — Weekly Video Digest")
        self.assertEqual(len(embed["fields"]), 1)
        self.assertIn("Watch on YouTube", embed["fields"][0]["value"])

    def test_build_blog_embed_contains_expected_fields(self) -> None:
        now = datetime.now(tz=timezone.utc)
        embed = build_blog_embed(
            posts=[
                {
                    "title": "GitHub Security News",
                    "summary": "A new security feature has shipped.",
                    "url": "https://github.blog/post",
                    "published": "2026-05-01",
                }
            ],
            keywords=["Security"],
            since=now,
            now=now,
        )

        self.assertEqual(embed["title"], "📝 GitHub — Weekly Blog Digest")
        self.assertEqual(len(embed["fields"]), 1)
        self.assertIn("Read on GitHub Blog", embed["fields"][0]["value"])


if __name__ == "__main__":
    unittest.main()
