# DevRel Discord Bot

A Discord bot that watches the **GitHub YouTube channel** and the **GitHub Blog** for new content, then posts rich summary embeds to a Discord channel of your choosing.

## Features

- 🎬 **Weekly YouTube digest** — every Thursday night the bot searches the GitHub YouTube channel for the top **Copilot** videos from the past 7 days, ranks them by view count, and posts a digest embed (default: top 3).
- 📝 **Weekly blog digest** — same schedule; filters the GitHub Blog RSS feed for **Copilot** posts from the past 7 days and posts the most recent ones.
- 🔒 **Secure by default** — secrets live in `.env` (gitignored) or host environment variables; never in source control.
- ⚙️ **Configurable** – poll intervals, channel IDs, and feed URLs are all in `config/config.yaml`.
- 🐳 **Docker-ready** – includes a multi-stage `Dockerfile` and `docker-compose.yml`.

## Quick start

```bash
cp .env.example .env          # fill in DISCORD_TOKEN and YOUTUBE_API_KEY
# edit config/config.yaml with your Discord channel IDs
pip install -r requirements.txt
python main.py
```

See **[SETUP.md](SETUP.md)** for the full setup guide, including:

- How to create a Discord bot application and get a token
- How to enable the YouTube Data API v3 and create an API key
- Hosting options: **Azure Container Apps**, **Azure App Service**, **Railway**, **Fly.io**, **Heroku**
- Security notes and troubleshooting tips
