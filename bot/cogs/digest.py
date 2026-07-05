import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

class DigestCommand(commands.Cog):
    """Cog containing the unified /digest manual trigger command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="digest",
        description="Manually run the content digests right now.",
    )
    @app_commands.describe(
        source="Which digest to run (all, youtube, blog)"
    )
    @app_commands.choices(source=[
        app_commands.Choice(name="All Sources", value="all"),
        app_commands.Choice(name="YouTube Only", value="youtube"),
        app_commands.Choice(name="Blog Only", value="blog"),
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def digest(self, interaction: discord.Interaction, source: app_commands.Choice[str] = None) -> None:
        """Slash command to trigger the digests immediately."""
        choice = source.value if source else "all"
        
        youtube_cog = self.bot.get_cog("YouTubeWatcher")
        blog_cog = self.bot.get_cog("BlogWatcher")
        
        await interaction.response.defer(ephemeral=True)

        responses = []
        
        if choice in ("all", "youtube"):
            if youtube_cog:
                _, msg = await youtube_cog.trigger_manual_digest(interaction.user)
                responses.append(msg)
            else:
                responses.append("❌ YouTubeWatcher cog is not loaded.")
                
        if choice in ("all", "blog"):
            if blog_cog:
                _, msg = await blog_cog.trigger_manual_digest(interaction.user)
                responses.append(msg)
            else:
                responses.append("❌ BlogWatcher cog is not loaded.")

        if not responses:
            await interaction.followup.send("No actions were taken.", ephemeral=True)
            return

        final_msg = "\n".join(responses)
        await interaction.followup.send(final_msg, ephemeral=True)

# Required by discord.py to load the cog.
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DigestCommand(bot))
