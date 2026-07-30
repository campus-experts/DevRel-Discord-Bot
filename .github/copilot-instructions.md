# Copilot Instructions

## Deployment

- This is a short-lived Python digest job, not a continuously running Discord server.
- On SparkedHost, the cron job starts the SparkedHost server. Set the server's beginning command to:

  ```bash
  python main.py
  ```

- `main.py` fetches the GitHub Blog and YouTube data, posts the configured Discord embeds, and exits. The SparkedHost server is expected to shut down after the command exits.
- Run the command from the repository root. `main.py` resolves `config/config.yaml` as a relative path.

## Secrets and configuration

- Keep `DISCORD_TOKEN` and `YOUTUBE_API_KEY` in SparkedHost environment secrets or a local `.env` file.
- Never commit, print, or expose secret values in source code, logs, tool output, or documentation.
- Non-secret settings, including Discord channel IDs, feed settings, keywords, and digest sizes, belong in `config/config.yaml`.

## Architecture

- `main.py` is the orchestration and process entry point. It loads environment variables and YAML configuration, fetches both content sources, posts to Discord through its HTTP API, and returns a nonzero exit status on failure.
- `utils/blog_fetcher.py` reads and filters the GitHub Blog RSS feed.
- `utils/youtube_api.py` uses YouTube Data API v3 to find recent uploads and rank them by view count.
- `utils/embeds.py` builds the Discord embed payloads.
- The job is intentionally invoked by an external weekly schedule; it does not require a Discord gateway connection or a web server.

## Development commands

From the repository root:

```bash
pip install -r requirements.txt
python -m compileall -q main.py bot utils tests
python -m unittest discover -s tests -v
```

Run an individual test module with:

```bash
python -m unittest tests.test_youtube_api -v
```
