"""
bot/bot.py – Discord bot class for the DevRel content bot.

This module defines ``DevRelBot``, a thin subclass of
``discord.ext.commands.Bot`` that:

  - Accepts the parsed ``config.yaml`` at construction time so every cog
    can access settings via ``self.bot.config``.
  - Loads all cogs (extensions) listed in ``COGS`` during ``setup_hook``
    so they are ready before the bot connects to the Gateway.
  - Logs a confirmation message when the bot is ready.
"""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# Dotted module paths for every cog to load.
# Add new cogs here to register them automatically.
COGS = [
    "bot.cogs.youtube_watcher",
    "bot.cogs.blog_watcher",
]


class DevRelBot(commands.Bot):
    """Custom Discord bot for DevRel content delivery.

    Args:
        config: Parsed contents of ``config/config.yaml``.
    """

    def __init__(self, config: dict) -> None:
        # Only request the intents the bot actually needs.
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config: dict = config

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def setup_hook(self) -> None:
        """Load all cogs before the bot connects to Discord."""
        for cog_path in COGS:
            try:
                await self.load_extension(cog_path)
                logger.info("Loaded cog: %s", cog_path)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to load cog %s: %s", cog_path, exc)

    async def on_ready(self) -> None:
        """Called when the bot has successfully connected to Discord."""
        logger.info(
            "Logged in as %s (ID: %s) — watching for new content!",
            self.user,
            self.user.id,
        )
