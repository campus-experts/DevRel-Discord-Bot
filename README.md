# DevRel Discord Bot

A Discord bot that watches the **GitHub YouTube channel** and the **GitHub Blog** for new content, then posts weekly topic digests to a Discord channel of your choosing.

## Features

- 🎬 **Weekly YouTube digest** — every Thursday the bot searches the GitHub YouTube channel for the top videos from the past 7 days matching any of the configured topics, ranks them by view count, and posts a digest embed (default: top 3).
- 📝 **Weekly blog digest** — same Thursday schedule; filters the GitHub Blog RSS feed for posts matching any configured topic from the past 7 days and posts the most recent ones.
- 🏷️ **Multi-topic filtering** — out of the box the bot covers **GitHub Copilot**, **GitHub Copilot CLI**, **Security**, **Developer Skills**, and **Company News** (fully configurable in `config/config.yaml`).
- ⏰ **Cron-ready** — runs once on Thursday, posts both digests, and exits; no continuously running process is required.
- 🔒 **Secure by default** — secrets live in `.env` (gitignored) or host environment variables; never in source control.
- ⚙️ **Configurable** — digest day, topics, channel IDs, and feed URL are all in `config/config.yaml`.

## Quick start

```bash
cp .env.example .env          # fill in DISCORD_TOKEN and YOUTUBE_API_KEY
# edit config/config.yaml with your Discord channel IDs
pip install -r requirements.txt
python main.py
```

Configure Sparked Host to run `python main.py` from the repository root every
Thursday. The script fetches both sources, posts through the Mona Media bot
token using Discord's HTTP API, and exits.

See **[SETUP.md](SETUP.md)** for the full setup guide, including:

- How to create a Discord bot application and get a token
- How to enable the YouTube Data API v3 and create an API key
- Security notes and troubleshooting tips
