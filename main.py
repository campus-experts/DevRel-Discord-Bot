"""
main.py – Entry point for the DevRel Discord Bot.

Quick-start
───────────
1. Copy ``.env.example`` to ``.env`` and fill in your secrets::

       cp .env.example .env
       # edit .env with your DISCORD_TOKEN and YOUTUBE_API_KEY

2. Edit ``config/config.yaml`` with your Discord channel IDs.

3. Install dependencies::

       pip install -r requirements.txt

4. Run the bot::

       python main.py

The bot will:
  - Load environment variables from ``.env`` (ignored if the file is absent –
    in production, set variables directly in the host environment).
  - Read non-secret configuration from ``config/config.yaml``.
  - Connect to Discord for one digest run and then disconnect.
"""

import logging
import asyncio
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from bot.cron_runner import run_cron_job

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path("config/config.yaml")


def _load_config(path: Path = _CONFIG_PATH) -> dict:
    """Parse and return the YAML configuration file."""
    if not path.exists():
        logger.critical("Configuration file not found: %s", path)
        sys.exit(1)
    with path.open() as fh:
        try:
            config = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            logger.critical("Configuration file contains invalid YAML: %s\n%s", path, exc)
            sys.exit(1)
    if not isinstance(config, dict):
        logger.critical("Configuration file is empty or malformed: %s", path)
        sys.exit(1)
    return config


def _validate_env() -> None:
    """Exit with a helpful message if required environment variables are missing."""
    required = ["DISCORD_TOKEN", "YOUTUBE_API_KEY"]
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        logger.critical(
            "Required environment variables are not set: %s\n"
            "Copy .env.example to .env and fill in the values.",
            ", ".join(missing),
        )
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # Load .env if it exists. In hosted deployments, secrets can be injected
    # directly into the environment instead.
    load_dotenv()

    _validate_env()
    config = _load_config()

    asyncio.run(run_cron_job(config, os.environ["DISCORD_TOKEN"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Digest job failed.")
        raise SystemExit(1)
