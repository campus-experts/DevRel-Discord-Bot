# Run DevRel Discord Bot Locally (Today)

This is the quickest path to get the bot running on your machine.

You need:
- A **Discord account** (for bot/app creation)
- A **Google account** (for YouTube API access)

## 1. Create the Discord bot token

1. Go to https://discord.com/developers/applications and sign in.
2. Click **New Application**.
3. Open **Bot** in the left menu, then click **Add Bot**.
4. Under **Token**, generate/copy the token (`DISCORD_TOKEN`).
5. Invite the bot to your server:
   - Open **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`
   - Open the generated URL and authorize the bot for your server.
6. In Discord, enable **Developer Mode**, then copy the IDs for the channels where digests should post.

## 2. Create the YouTube API key

1. Go to https://console.cloud.google.com/ and sign in.
2. Create/select a project.
3. Enable **YouTube Data API v3**.
4. Create an API key (`YOUTUBE_API_KEY`).
5. Recommended: restrict the key to YouTube Data API v3.

## 3. Configure this repository

From project root:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DISCORD_TOKEN=your-discord-bot-token
YOUTUBE_API_KEY=your-youtube-api-key
```

Edit `config/config.yaml`:
- Set real `discord_channel_id` values for `youtube` and `blog`.
- Optionally adjust `keywords`, `digest_count`, and `search_pool`.

## 4. Install dependencies and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 5. What to expect right away

- The process logs in, posts the configured digests when run on Thursday, and exits.
- Run it from the project root so `config/config.yaml` resolves correctly.
