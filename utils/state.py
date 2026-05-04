"""
utils/state.py – Shared helpers for persisting bot state.

The bot stores small pieces of state, such as the last digest dates for
YouTube and blog content, in ``data/state.json`` across restarts. This
avoids re-sending content that has already been covered by a previous digest
after a reboot.

The data/ directory is listed in .gitignore so state is never committed.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default path; can be overridden by passing a custom path to the functions.
_DEFAULT_STATE_FILE = Path("data/state.json")


def load_state(path: Path = _DEFAULT_STATE_FILE) -> dict:
    """Load persisted state from *path*.  Returns an empty dict if missing."""
    if path.exists():
        try:
            with path.open() as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read state file %s: %s", path, exc)
    return {}


def save_state(state: dict, path: Path = _DEFAULT_STATE_FILE) -> None:
    """Persist *state* to *path*, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fh:
            json.dump(state, fh, indent=2)
    except OSError as exc:
        logger.error("Could not write state file %s: %s", path, exc)
