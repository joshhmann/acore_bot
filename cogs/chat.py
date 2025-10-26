"""Chat cog for Ollama-powered conversations."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

from config import Config
from services.ollama import OllamaService
from utils.helpers import ChatHistoryManager, chunk_message, format_error, format_success

logger = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """Cog for chat commands using Ollama."""

    def __init__(self, bot: commands.Bot, ollama: OllamaService, history_manager: ChatHistoryManager):
        """Initialize chat cog.

        Args:
            bot: Discord bot instance
            ollama: Ollama service instance
            history_manager: Chat history manager
        """
        self.bot = bot
        self.ollama = ollama
        self.history = history_manager
        self.system_prompt = (
            "You are a helpful AI assistant in a Discord server. "
            "Keep your responses concise and friendly. "
            "You can use Discord markdown for formatting."
        )

    @app_commands.command(name="chat", description="Chat with the AI")
    @app_commands.describe(message="Your message to the AI")
    async def chat(self, interaction: discord.Interaction, message: str):
        """Chat with Ollama AI.

        Args:
            interaction: Discord interaction
            message: User's message
        """
        await interaction.response.defer(thinking=True)

        try:
            channel_id = interaction.channel_id

            # Load conversation history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(channel_id)

            # Add user message
            history.append({"role": "user", "content": message})

            # Get AI response
            response = await self.ollama.chat(history, system_prompt=self.system_prompt)

            # Save to history
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(channel_id, "user", message)
                await self.history.add_message(channel_id, "assistant", response)

            # Send response (handle long messages)
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Chat command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="ask", description="Ask the AI a question (no history)")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a one-off question without using conversation history.

        Args:
            interaction: Discord interaction
            question: User's question
        """
        await interaction.response.defer(thinking=True)

        try:
            response = await self.ollama.generate(question, system_prompt=self.system_prompt)

            # Send response
            chunks = await chunk_message(response)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)

        except Exception as e:
            logger.error(f"Ask command failed: {e}")
            await interaction.followup.send(format_error(e))

    @app_commands.command(name="clear_history", description="Clear conversation history for this channel")
    async def clear_history(self, interaction: discord.Interaction):
        """Clear chat history for the current channel.

        Args:
            interaction: Discord interaction
        """
        try:
            channel_id = interaction.channel_id
            await self.history.clear_history(channel_id)
            await interaction.response.send_message(
                format_success("Conversation history cleared!"), ephemeral=True
            )
        except Exception as e:
            logger.error(f"Clear history failed: {e}")
            await interaction.response.send_message(format_error(e), ephemeral=True)

    @app_commands.command(name="set_model", description="Change the Ollama model")
    @app_commands.describe(model="Model name (e.g., llama3.2, mistral, etc.)")
    async def set_model(self, interaction: discord.Interaction, model: str):
        """Change the active Ollama model.

        Args:
            interaction: Discord interaction
            model: Name of the model to use
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # Check if model is available
            models = await self.ollama.list_models()

            if model not in models:
                available = ", ".join(models) if models else "None found"
                await interaction.followup.send(
                    f"❌ Model '{model}' not found.\n\nAvailable models: {available}",
                    ephemeral=True,
                )
                return

            # Update model
            self.ollama.model = model
            await interaction.followup.send(
                format_success(f"Model changed to: **{model}**"), ephemeral=True
            )

        except Exception as e:
            logger.error(f"Set model failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="models", description="List available Ollama models")
    async def models(self, interaction: discord.Interaction):
        """List all available models.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            models = await self.ollama.list_models()

            if not models:
                await interaction.followup.send("❌ No models found on Ollama server.", ephemeral=True)
                return

            current = self.ollama.model
            model_list = "\n".join([f"{'🟢' if m == current else '⚪'} {m}" for m in models])

            embed = discord.Embed(
                title="Available Ollama Models",
                description=model_list,
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Current model: {current}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Models command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @app_commands.command(name="status", description="Check AI status")
    async def status(self, interaction: discord.Interaction):
        """Check Ollama service status.

        Args:
            interaction: Discord interaction
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            healthy = await self.ollama.check_health()

            if healthy:
                embed = discord.Embed(
                    title="🟢 AI Status: Online",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Server", value=self.ollama.host)
                embed.add_field(name="Model", value=self.ollama.model)
                embed.add_field(name="Temperature", value=f"{self.ollama.temperature}")
            else:
                embed = discord.Embed(
                    title="🔴 AI Status: Offline",
                    description=f"Cannot connect to Ollama at {self.ollama.host}",
                    color=discord.Color.red(),
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Status command failed: {e}")
            await interaction.followup.send(format_error(e), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages to enable auto-reply.

        Args:
            message: Discord message
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if auto-reply is enabled for this channel
        if not Config.AUTO_REPLY_ENABLED:
            return

        if Config.AUTO_REPLY_CHANNELS and message.channel.id not in Config.AUTO_REPLY_CHANNELS:
            return

        # Check if bot is mentioned
        if self.bot.user not in message.mentions:
            return

        try:
            # Load history
            history = []
            if Config.CHAT_HISTORY_ENABLED:
                history = await self.history.load_history(message.channel.id)

            # Add user message
            user_content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            history.append({"role": "user", "content": user_content})

            # Get response
            async with message.channel.typing():
                response = await self.ollama.chat(history, system_prompt=self.system_prompt)

            # Save to history
            if Config.CHAT_HISTORY_ENABLED:
                await self.history.add_message(message.channel.id, "user", user_content)
                await self.history.add_message(message.channel.id, "assistant", response)

            # Send response
            chunks = await chunk_message(response)
            for chunk in chunks:
                await message.channel.send(chunk)

        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
            await message.channel.send(format_error(e))


async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    # This will be called from main.py with proper dependencies
    pass
