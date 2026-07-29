"""Discord embed payload builders."""


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _fmt_views(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K views"
    return f"{count:,} views"


def build_blog_embed(posts: list, keywords: list[str], since, now) -> dict:
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    embed = {
        "title": "📝 GitHub — Weekly Blog Digest",
        "description": (
            f"Recent GitHub Blog posts from the past week ({date_range}).\n"
            f"**Topics:** {', '.join(keywords)}"
        ),
        "color": 0x2EA44F,
        "author": {
            "name": "GitHub Blog",
            "url": "https://github.blog",
            "icon_url": "https://github.githubassets.com/favicons/favicon.png",
        },
        "fields": [],
        "footer": {"text": "GitHub Blog • Weekly Digest"},
    }
    medals = ["🥇", "🥈", "🥉"]
    for i, post in enumerate(posts):
        published = f"Published: {post['published']}\n" if post.get("published") else ""
        embed["fields"].append(
            {
                "name": f"{medals[i] if i < len(medals) else f'#{i + 1}'} {post['title']}",
                "value": (
                    f"[📖 Read on GitHub Blog]({post['url']})\n"
                    f"{published}{_truncate(post['summary'], 200) or '*No summary.*'}"
                ),
                "inline": False,
            }
        )
    return embed


def build_youtube_embed(videos: list, since, now) -> dict:
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    embed = {
        "title": "📺 GitHub — Weekly Video Digest",
        "description": (
            f"Top GitHub YouTube videos from the past week ({date_range}), "
            "ranked by views."
        ),
        "color": 0xFF0000,
        "author": {
            "name": "GitHub on YouTube",
            "url": "https://www.youtube.com/@GitHub",
            "icon_url": "https://www.youtube.com/favicon.ico",
        },
        "fields": [],
        "footer": {"text": "GitHub YouTube Channel • Weekly Digest"},
    }
    medals = ["🥇", "🥈", "🥉"]
    for i, video in enumerate(videos):
        embed["fields"].append(
            {
                "name": f"{medals[i] if i < len(medals) else f'#{i + 1}'} {video['title']}",
                "value": (
                    f"[▶ Watch on YouTube]({video['url']}) • "
                    f"{_fmt_views(video.get('view_count', 0))}\n"
                    f"{_truncate(video['description'], 200) or '*No description.*'}"
                ),
                "inline": False,
            }
        )
    if videos and videos[0].get("thumbnail"):
        embed["image"] = {"url": videos[0]["thumbnail"]}
    return embed
