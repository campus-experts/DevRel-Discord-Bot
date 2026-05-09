import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from utils.blog_fetcher import BlogFetcher, _strip_html


class Entry(dict):
    def __getattr__(self, item):
        return self.get(item)


def _parsed_time(days_ago: int):
    dt = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return dt.timetuple()


class BlogFetcherTests(unittest.TestCase):
    def test_strip_html_removes_tags_and_collapses_whitespace(self) -> None:
        text = "<p>Hello</p>\n<div>world</div>   <b>!</b>"
        self.assertEqual(_strip_html(text), "Hello world !")

    def test_get_posts_since_by_keywords_filters_by_date_and_keyword(self) -> None:
        fetcher = BlogFetcher("https://example.test/feed")
        feed = SimpleNamespace(
            bozo=False,
            entries=[
                Entry(
                    title="Copilot update",
                    summary="<p>Security improvements</p>",
                    link="https://example.test/1",
                    id="1",
                    published="now",
                    published_parsed=_parsed_time(1),
                ),
                Entry(
                    title="Unrelated post",
                    summary="No matching keyword",
                    link="https://example.test/2",
                    id="2",
                    published="now",
                    published_parsed=_parsed_time(1),
                ),
                Entry(
                    title="Old Copilot post",
                    summary="Still Copilot but too old",
                    link="https://example.test/3",
                    id="3",
                    published="old",
                    published_parsed=_parsed_time(10),
                ),
            ],
        )

        since = datetime.now(tz=timezone.utc) - timedelta(days=7)
        with patch("utils.blog_fetcher.feedparser.parse", return_value=feed):
            posts = fetcher.get_posts_since_by_keywords(
                since=since, keywords=["Copilot"], max_results=3, search_pool=20
            )

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "1")
        self.assertEqual(posts[0]["url"], "https://example.test/1")

    def test_get_posts_since_by_keywords_skips_entries_without_parsed_date(self) -> None:
        fetcher = BlogFetcher("https://example.test/feed")
        feed = SimpleNamespace(
            bozo=False,
            entries=[
                Entry(
                    title="Copilot update",
                    summary="Missing parsed date",
                    link="https://example.test/1",
                    id="1",
                    published="now",
                ),
            ],
        )

        since = datetime.now(tz=timezone.utc) - timedelta(days=7)
        with patch("utils.blog_fetcher.feedparser.parse", return_value=feed):
            posts = fetcher.get_posts_since_by_keywords(
                since=since, keywords=["Copilot"], max_results=3, search_pool=20
            )
        self.assertEqual(posts, [])

    def test_get_posts_since_by_keywords_requires_timezone_aware_since(self) -> None:
        fetcher = BlogFetcher("https://example.test/feed")
        with self.assertRaises(ValueError):
            fetcher.get_posts_since_by_keywords(
                since=datetime.now(), keywords=["Copilot"], max_results=3
            )


if __name__ == "__main__":
    unittest.main()
