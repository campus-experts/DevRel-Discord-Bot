"""Discord embed builders for the blog and YouTube digests."""

import discord


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


def build_blog_embed(posts: list, keywords: list[str], since, now) -> discord.Embed:
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    embed = discord.Embed(
        title="📝 GitHub — Weekly Blog Digest",
        description=(
            f"Recent GitHub Blog posts from the past week ({date_range}).\n"
            f"**Topics:** {', '.join(keywords)}"
        ),
        color=discord.Color.green(),
    )
    embed.set_author(
        name="GitHub Blog",
        url="https://github.blog",
        icon_url="https://github.githubassets.com/favicons/favicon.png",
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, post in enumerate(posts):
        medal = medals[i] if i < len(medals) else f"#{i + 1}"
        published = f"Published: {post['published']}\n" if post.get("published") else ""
        embed.add_field(
            name=f"{medal} {post['title']}",
            value=(
                f"[📖 Read on GitHub Blog]({post['url']})\n"
                f"{published}"
                f"{_truncate(post['summary'], 200) or '*No summary.*'}"
            ),
            inline=False,
        )
    embed.set_footer(text="GitHub Blog • Weekly Digest")
    return embed


def build_youtube_embed(videos: list, since, now) -> discord.Embed:
    date_range = f"{since.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    embed = discord.Embed(
        title="📺 GitHub — Weekly Video Digest",
        description=(
            f"Top GitHub YouTube videos from the past week ({date_range}), "
            "ranked by views."
        ),
        color=discord.Color.red(),
    )
    embed.set_author(
        name="GitHub on YouTube",
        url="https://www.youtube.com/@GitHub",
        icon_url="https://www.youtube.com/favicon.ico",
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, video in enumerate(videos):
        medal = medals[i] if i < len(medals) else f"#{i + 1}"
        embed.add_field(
            name=f"{medal} {video['title']}",
            value=(
                f"[▶ Watch on YouTube]({video['url']}) • "
                f"{_fmt_views(video.get('view_count', 0))}\n"
                f"{_truncate(video['description'], 200) or '*No description.*'}"
            ),
            inline=False,
        )
        if i == 0 and video.get("thumbnail"):
            embed.set_image(url=video["thumbnail"])
    embed.set_footer(text="GitHub YouTube Channel • Weekly Digest")
    return embed
