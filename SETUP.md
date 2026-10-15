# DevRel Discord Bot - Setup Guide

This project runs as a short-lived Python process. A scheduled invocation
gathers the GitHub Blog and YouTube digests, posts them through Discord's HTTP
API, and exits. It does not require a continuously running bot or Docker.

## Prerequisites

- Python 3.11 or newer
- A Discord bot with `Send Messages` and `Embed Links` permissions
- A YouTube Data API v3 key
- A host that can run a weekly cron job

## Configure Discord

1. Create a Discord application and bot in the
   [Discord Developer Portal](https://discord.com/developers/applications).
2. Copy the bot token as `DISCORD_TOKEN`.
3. Enable Developer Mode in Discord and copy the destination channel IDs.
4. Set the `discord_channel_id` values in `config/config.yaml`.

### Optional Campus Expert role tag

Copy the Campus Expert role ID from the server's role settings with Developer
Mode enabled. Set `blog.mention_role_id` in `config/config.yaml` to that numeric
ID in quotes, not the role name. Leave it `null` to post without a tag.

The bot needs `View Channel`, `Send Messages`, and `Embed Links` in the destination
channel. To tag a role that is not mentionable by everyone, it also needs
`Mention @everyone, @here, and All Roles` there. If it already has that permission,
no extra permission is needed. Do not grant Administrator or Manage Roles or
make the role mentionable by everyone for this change.

The blog message allows only the configured role to be notified. It does not
notify everyone, here, other roles, or individual users. YouTube never tags the
role, even if no blog posts are found. Repeated runs can post and tag again.
Members' notification settings can suppress push notifications.

## Configure YouTube

1. Enable YouTube Data API v3 in the
   [Google Cloud Console](https://console.cloud.google.com/).
2. Create an API key as `YOUTUBE_API_KEY`.
3. Restrict the key to YouTube Data API v3 when possible.

## Install and test locally

```bash
git clone https://github.com/campus-experts/DevRel-Discord-Bot.git
cd DevRel-Discord-Bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DISCORD_TOKEN` and `YOUTUBE_API_KEY` in `.env`, then run:

```bash
python main.py
```

The job looks back seven days and posts both digests whenever it is invoked.
The cron schedule is responsible for running it on Thursday.

## Sparked Host cron setup

Keep the existing weekly schedule that starts the Sparked Host server:

1. Runs on Thursday.
2. Starts the server with `python main.py` as its beginning command.
3. Uses the repository root as its working directory.
4. Provides `DISCORD_TOKEN` and `YOUTUBE_API_KEY`.

The process posts the digests and exits. The server is expected to shut down
afterward; it does not need to remain running.

Equivalent command:

```bash
cd /path/to/DevRel-Discord-Bot && /path/to/python main.py
```

To deploy the role tag, upload the updated application and configuration files
through your existing deployment method, then set the real `blog.mention_role_id`
on Sparked Host. Keep the existing schedule, beginning command, and secrets.
Coordinate one live check: the blog message should show @Campus Expert, YouTube
should have no tag, and the process should exit as before. This check notifies
real members, so do not repeatedly start the production job for testing.

Clear `blog.mention_role_id` to disable the tag.

## Configuration

`config/config.yaml` controls:

- GitHub YouTube channel and Discord destination
- GitHub Blog feed and Discord destination
- Blog keywords
- Optional blog role ID to tag
- Number of entries and candidate search pool

The process expects these environment variables:

```dotenv
DISCORD_TOKEN=your-discord-bot-token
YOUTUBE_API_KEY=your-youtube-api-key
```

## Project structure

```text
DevRel-Discord-Bot/
├── bot/
│   └── __init__.py
├── config/config.yaml       # Non-secret configuration
├── utils/
│   ├── blog_fetcher.py      # GitHub Blog RSS fetcher
│   ├── embeds.py            # Discord embed builders
│   └── youtube_api.py       # YouTube API wrapper
├── main.py                  # Cron script: fetch, post, exit
├── requirements.txt
└── tests/
```

## Troubleshooting

**No messages are posted**

- Confirm the cron job runs on Thursday UTC.
- Confirm both channel IDs are correct.
- Confirm the bot has `Send Messages` and `Embed Links` permissions.
- Check the cron process output for API or Discord errors.

**`KeyError: 'YOUTUBE_API_KEY'`**

- Set the variable in Sparked Host's job environment or in a local `.env`.

**YouTube API `403`**

- Confirm YouTube Data API v3 is enabled and the key has remaining quota.
