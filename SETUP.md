# DevRel Discord Bot – Setup & Hosting Guide

A Discord bot that watches the **GitHub YouTube channel** and the **GitHub Blog** for new content, then posts a rich summary embed to a channel of your choosing.

---

## Table of Contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Step 1 – Create a Discord Application & Bot](#step-1--create-a-discord-application--bot)
4. [Step 2 – Enable the YouTube Data API](#step-2--enable-the-youtube-data-api)
5. [Step 3 – Clone & configure the project](#step-3--clone--configure-the-project)
6. [Step 4 – Run locally](#step-4--run-locally)
7. [Step 5 – Run with Docker](#step-5--run-with-docker)
8. [Hosting options](#hosting-options)
   - [Azure Container Apps (recommended)](#azure-container-apps-recommended)
   - [Azure App Service](#azure-app-service)
   - [Railway](#railway)
   - [Fly.io](#flyio)
   - [Heroku](#heroku)
9. [Project structure](#project-structure)
10. [Security notes](#security-notes)
11. [Troubleshooting](#troubleshooting)

---

## How it works

```
┌─────────────────────────────────────────────────────┐       ┌───────────────────┐
│  DevRel Discord Bot                                  │  →    │  Discord Channel  │
│                                                      │       └───────────────────┘
│  YouTubeWatcher cog                                  │
│    └─ checks once daily; posts on Thursday a digest  │
│       of top videos from the past 7 days matching    │
│       any configured topic, ranked by view count     │
│                                                      │
│  BlogWatcher cog                                     │
│    └─ checks once daily; posts on Thursday a digest  │
│       of the most recent blog posts from the past    │
│       7 days matching any configured topic           │
└─────────────────────────────────────────────────────┘
```

- The bot runs a **daily check** at midnight UTC — cost-effective with no unnecessary wakeups.
- On Thursday it searches for content matching **any** of the configured topics published in the past 7 days.
- Default topics: **GitHub Copilot**, **GitHub Copilot CLI**, **Security**, **Developer Skills**, **Company News**.
- For **YouTube**: candidates are ranked by **view count** and the top 2–3 are included in a single embed.
- For the **Blog**: RSS feeds don't carry view-count data, so the 2–3 most recent matching posts are used.
- A digest date is saved to `data/state.json` so the bot won't re-post if it restarts on the same Thursday.

> The digest day, topic keywords, and digest size are all configurable in `config/config.yaml`.

---

## Prerequisites

| Tool | Minimum version | Notes |
|------|----------------|-------|
| Python | 3.11 | 3.12 recommended |
| pip | 23+ | comes with Python |
| Docker (optional) | 24+ | for containerised deployment |
| A Discord account | – | needed to create the bot application |
| A Google account | – | needed for the YouTube API key |

---

## Step 1 – Create a Discord Application & Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**.
2. Give it a name (e.g. *DevRel Bot*) and click **Create**.
3. In the left sidebar click **Bot**, then **Add Bot** → **Yes, do it!**
4. Under **Token** click **Reset Token**, copy the value and save it somewhere safe – this is your `DISCORD_TOKEN`.

   > ⚠️ Never share this token. Treat it like a password.

5. Under **Privileged Gateway Intents**, enable **Server Members Intent** if you want the bot to see member info (not required for this bot), then **Save Changes**.

6. **Invite the bot to your server:**
   - In the sidebar click **OAuth2 → URL Generator**.
   - Under *Scopes* tick **bot** and **applications.commands**.
   - Under *Bot Permissions* tick **Send Messages** and **Embed Links**.
   - Copy the generated URL, open it in a browser, select your server, and click **Authorise**.

7. **Find your Discord channel IDs:**
   - In Discord, go to *User Settings → Advanced* and enable **Developer Mode**.
   - Right-click the channel you want to receive YouTube announcements → **Copy Channel ID**.
   - Repeat for the blog announcements channel.
   - Paste both IDs into `config/config.yaml`.

---

## Step 2 – Enable the YouTube Data API

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a new project (or select an existing one).
2. Go to **APIs & Services → Library**, search for *YouTube Data API v3*, and click **Enable**.
3. Go to **APIs & Services → Credentials → Create Credentials → API key**.
4. Copy the key – this is your `YOUTUBE_API_KEY`.
5. **Restrict the key** (strongly recommended):
   - Click the key → **API restrictions → Restrict key → YouTube Data API v3**.
   - Optionally add an IP/HTTP-referrer restriction if you know your hosting IP.

---

## Step 3 – Clone & configure the project

```bash
# Clone the repository
git clone https://github.com/campus-experts/DevRel-Discord-Bot.git
cd DevRel-Discord-Bot

# Create your secrets file from the template
cp .env.example .env
```

Edit `.env`:

```dotenv
DISCORD_TOKEN=your-discord-bot-token-here
YOUTUBE_API_KEY=your-youtube-api-key-here
```

Edit `config/config.yaml` and replace the placeholder channel IDs:

```yaml
youtube:
  channel_id: "UC7c3Kb6jYCRj4JOHHZTxKsQ"   # GitHub's YouTube channel – change if needed
  discord_channel_id: 123456789012345678      # ← your real channel ID here
  digest_day: "thursday"                      # day of week to post the digest
  keywords:                                   # topics to match (OR logic)
    - "GitHub Copilot"
    - "GitHub Copilot CLI"
    - "Security"
    - "Developer Skills"
    - "Company News"
  digest_count: 3                             # videos to include in digest
  search_pool: 20                             # candidate pool before view-count ranking

blog:
  feed_url: "https://github.blog/feed/"
  discord_channel_id: 123456789012345679      # ← your real channel ID here
  digest_day: "thursday"
  keywords:
    - "GitHub Copilot"
    - "GitHub Copilot CLI"
    - "Security"
    - "Developer Skills"
    - "Company News"
  digest_count: 3
  search_pool: 20
```

> **Note:** YouTube channel IDs look like `UC7c3Kb6jYCRj4JOHHZTxKsQ`.  
> You can find a channel's ID at `https://www.youtube.com/@<handle>/about` (click the share icon → Copy channel ID), or via the [YouTube channel-ID finder](https://commentpicker.com/youtube-channel-id.php).

---

## Step 4 – Run locally

```bash
# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the bot
python main.py
```

You should see log output similar to:

```
2024-01-15 12:00:01 [INFO] bot.cogs.youtube_watcher: Loaded cog: bot.cogs.youtube_watcher
2024-01-15 12:00:01 [INFO] bot.cogs.blog_watcher: Loaded cog: bot.cogs.blog_watcher
2024-01-15 12:00:01 [INFO] bot.bot: Logged in as DevRelBot#1234 (ID: 987654321) — watching for new content!
```

Press **Ctrl+C** to stop.

---

## Step 5 – Run with Docker

```bash
# Build the image
docker build -t devrel-discord-bot .

# Run (secrets via environment variables)
docker run --rm \
  -e DISCORD_TOKEN="your-token" \
  -e YOUTUBE_API_KEY="your-key" \
  devrel-discord-bot
```

Or using Docker Compose (reads from `.env` automatically):

```bash
docker compose up --build
```

State (`data/state.json`) is stored in a named volume `bot_data` so it survives container restarts.

---

## Hosting options

### Azure Container Apps *(recommended)*

Azure Container Apps is a good fit for this bot, but it should be configured to keep at least one replica running. Discord bots need to maintain an active Gateway connection, so scaling to zero would stop the bot from receiving events and running its scheduled digest checks.

```bash
# 1. Install the Azure CLI
#    https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# 2. Login
az login

# 3. Create a resource group and Container Apps environment
az group create --name rg-devrel-bot --location eastus
az containerapp env create \
  --name devrel-bot-env \
  --resource-group rg-devrel-bot \
  --location eastus

# 4. Push your image to Azure Container Registry
az acr create --resource-group rg-devrel-bot \
  --name devrelbotreg --sku Basic
az acr login --name devrelbotreg
docker tag devrel-discord-bot devrelbotreg.azurecr.io/devrel-discord-bot:latest
docker push devrelbotreg.azurecr.io/devrel-discord-bot:latest

# 5. Deploy (secrets injected securely via --secrets / --env-vars)
az containerapp create \
  --name devrel-discord-bot \
  --resource-group rg-devrel-bot \
  --environment devrel-bot-env \
  --image devrelbotreg.azurecr.io/devrel-discord-bot:latest \
  --registry-server devrelbotreg.azurecr.io \
  --secrets discord-token="<DISCORD_TOKEN>" youtube-api-key="<YOUTUBE_API_KEY>" \
  --env-vars "DISCORD_TOKEN=secretref:discord-token" \
             "YOUTUBE_API_KEY=secretref:youtube-api-key" \
  --min-replicas 1 \
  --max-replicas 1
```

> Secrets are stored in the Container Apps secret store and never appear in environment-variable plaintext in the portal.

---

### Azure App Service

Azure App Service supports Docker containers and offers the **Key Vault** integration for secrets.

1. Create an App Service Plan (B1 or higher for always-on).
2. Create a Web App → **Docker Container** → your ACR image.
3. Under **Configuration → Application settings** add `DISCORD_TOKEN` and `YOUTUBE_API_KEY` as app settings (they are encrypted at rest).
4. Enable **Always On** so the bot doesn't sleep.

> For production use, consider pulling secrets from **Azure Key Vault** using a managed identity rather than storing them directly as app settings.

---

### Railway

[Railway](https://railway.app) is the quickest option for hobby projects.

1. Push your code to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. In the Railway dashboard, add environment variables:
   - `DISCORD_TOKEN`
   - `YOUTUBE_API_KEY`
4. Railway builds the Dockerfile automatically and deploys.

A persistent volume can be attached (`/app/data`) so state survives redeployments.

---

### Fly.io

[Fly.io](https://fly.io) provides Docker-based deployment close to your users.

```bash
# Install flyctl: https://fly.io/docs/getting-started/installing-flyctl/
fly auth login

fly launch --name devrel-discord-bot --no-deploy

# Set secrets (never stored in fly.toml)
fly secrets set DISCORD_TOKEN="your-token" YOUTUBE_API_KEY="your-key"

# Create a persistent volume for state.json
fly volumes create bot_data --size 1

# Deploy
fly deploy
```

Add to `fly.toml`:

```toml
[mounts]
  source      = "bot_data"
  destination = "/app/data"
```

---

### Heroku

1. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli).
2. ```bash
   heroku create devrel-discord-bot
   heroku config:set DISCORD_TOKEN="your-token" YOUTUBE_API_KEY="your-key"
   git push heroku main
   ```
3. Scale to a **worker** dyno (not web):
   ```bash
   heroku ps:scale web=0 worker=1
   ```

> ⚠️ Heroku's ephemeral filesystem means `data/state.json` is wiped on restart.  
> This bot currently persists state only by reading and writing `data/state.json`, so attaching Heroku Postgres or Redis alone will **not** preserve state without additional application code changes. On Heroku, either accept the trade-off of occasional re-posts after restarts or use a hosting option that provides a persistent disk mounted at `/app/data`.

---

## Project structure

```
DevRel-Discord-Bot/
├── .env.example            ← Copy to .env and fill in secrets
├── .gitignore
├── config/
│   └── config.yaml         ← Non-secret config (channel IDs, intervals)
├── bot/
│   ├── __init__.py
│   ├── bot.py              ← Discord bot class
│   └── cogs/
│       ├── __init__.py
│       ├── youtube_watcher.py  ← YouTube polling cog
│       └── blog_watcher.py     ← GitHub Blog RSS cog
├── utils/
│   ├── __init__.py
│   ├── youtube_api.py      ← YouTube Data API v3 wrapper
│   ├── blog_fetcher.py     ← RSS/Atom feed fetcher
│   └── state.py            ← Shared state persistence helpers
├── main.py                 ← Entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── SETUP.md                ← This file
```

---

## Security notes

| Concern | Mitigation |
|---------|-----------|
| Secrets in source control | `.env` is listed in `.gitignore`. Only `.env.example` (no real values) is committed. |
| Secrets in Docker image | Passed as runtime environment variables, never baked into the image. |
| YouTube API key exposure | Restrict the key to the YouTube Data API v3 in the Google Cloud Console. Optionally add an IP restriction. |
| Discord token exposure | Rotate via the Discord Developer Portal if compromised. |
| Least-privilege container | The Docker image runs as a non-root user (`botuser`). |
| State file | `data/` is gitignored. It currently stores only the last digest dates – no secrets. |

---

## Troubleshooting

**Bot goes online but no messages are posted**

- Make sure the `discord_channel_id` values in `config.yaml` match real channels in your server.
- Confirm the bot has **Send Messages** and **Embed Links** permissions in those channels.
- Check logs for `Discord channel ID … not found` errors.

**`KeyError: 'YOUTUBE_API_KEY'`**

- You forgot to create or populate `.env`. Copy `.env.example` → `.env` and set the value.

**`HttpError 403` from YouTube API**

- The API key may not have the YouTube Data API v3 enabled, or you've exceeded the daily quota (10 000 units by default). Check the [Google Cloud Console quotas page](https://console.cloud.google.com/iam-admin/quotas).

**Feed parse warning for GitHub Blog**

- This is a `feedparser` warning when the feed is slightly malformed. The bot continues and will still post entries if they are present.

**State file is lost after restart (Heroku)**

- Heroku has an ephemeral filesystem. See the [Heroku](#heroku) hosting notes above for options.
