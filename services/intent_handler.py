"""Intent handling service for processing detected user intents."""
import logging
import random
import math
from typing import Optional
from datetime import datetime
import discord

from config import Config
from services.intent_recognition import ConversationalResponder

logger = logging.getLogger(__name__)


class IntentHandler:
    """Handles processing of detected intents from user messages."""

    def __init__(self, bot):
        """Initialize intent handler.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot

    async def handle_math(self, intent) -> Optional[str]:
        """Handle math calculation.

        Args:
            intent: Math intent

        Returns:
            Result string or None
        """
        try:
            expression = intent.data['expression']
            groups = intent.data['groups']

            # Handle basic arithmetic
            if len(groups) >= 3:
                num1 = float(groups[0])
                op = groups[1]
                num2 = float(groups[2])

                # Normalize operators
                if op in ['×', '*']:
                    result = num1 * num2
                elif op in ['÷', '/']:
                    if num2 == 0:
                        return "Can't divide by zero! Nice try though 😄"
                    result = num1 / num2
                elif op == '+':
                    result = num1 + num2
                elif op == '-':
                    result = num1 - num2
                else:
                    return None

                # Format result
                if result.is_integer():
                    result = int(result)

                responses = [
                    f"That's **{result}**!",
                    f"**{result}**",
                    f"The answer is **{result}**",
                    f"**{result}** 🔢",
                    f"It's **{result}**!",
                ]
                return random.choice(responses)

            # Handle square root
            elif 'square root' in expression:
                num = float(groups[0])
                result = math.sqrt(num)
                if result.is_integer():
                    result = int(result)
                return f"The square root of {num} is **{result}**"

            # Handle squared/cubed
            elif 'squared' in expression:
                num = float(groups[0])
                result = num ** 2
                if result.is_integer():
                    result = int(result)
                return f"{num} squared is **{result}**"
            elif 'cubed' in expression:
                num = float(groups[0])
                result = num ** 3
                if result.is_integer():
                    result = int(result)
                return f"{num} cubed is **{result}**"

            return None

        except Exception as e:
            logger.error(f"Math calculation failed: {e}")
            return None

    async def handle_intent(self, intent, message: discord.Message) -> bool:
        """Handle a detected intent.

        Args:
            intent: Detected Intent object
            message: Discord message

        Returns:
            True if intent was fully handled, False to continue with AI response
        """
        try:
            if intent.intent_type == 'reminder':
                return await self._handle_reminder_intent(intent, message)

            elif intent.intent_type == 'reminder_no_time':
                # User wants a reminder but didn't specify time
                response = ConversationalResponder.generate_reminder_no_time_response()
                await message.channel.send(response)
                return True

            elif intent.intent_type == 'smalltalk':
                # Handle simple small talk without AI
                response = ConversationalResponder.generate_smalltalk_response(intent.data['message'])
                if response:
                    await message.channel.send(response)
                    return True
                # If no canned response, let AI handle it
                return False

            elif intent.intent_type == 'help':
                await self._handle_help_intent(message)
                return True

            elif intent.intent_type == 'math':
                # Handle math calculations
                result = await self.handle_math(intent)
                if result:
                    await message.channel.send(result)
                    return True
                return False

            elif intent.intent_type == 'time':
                await self._handle_time_intent(intent, message)
                return True

            elif intent.intent_type == 'trivia':
                return await self._handle_trivia_intent(message)

            elif intent.intent_type == 'music':
                # Handle music requests
                await message.channel.send(
                    f"Music commands work in voice channels! Try joining a voice channel and using `/play` or `/join` first."
                )
                return True

            elif intent.intent_type == 'search':
                # Let AI handle search with web search enabled
                return False

            elif intent.intent_type == 'weather':
                # Let AI handle weather queries
                return False

            elif intent.intent_type == 'translation':
                # Let AI handle translations
                return False

            elif intent.intent_type == 'custom':
                return await self._handle_custom_intent(intent, message)

            # Question and other intents - let AI handle them
            return False

        except Exception as e:
            logger.error(f"Failed to handle intent {intent.intent_type}: {e}")
            return False

    async def _handle_reminder_intent(self, intent, message: discord.Message) -> bool:
        """Handle reminder creation intent."""
        logger.info("Processing reminder intent")
        # Check if natural language reminders are enabled
        if not Config.NATURAL_LANGUAGE_REMINDERS:
            logger.warning("Natural language reminders are disabled in config")
            return False  # Let AI handle it

        # Handle reminder creation
        reminders_service = getattr(self.bot, 'reminders_service', None)
        if not reminders_service:
            logger.error("Reminders service not available")
            await message.channel.send("❌ Sorry, reminders aren't enabled on this bot.")
            return True

        trigger_time = intent.data['trigger_time']
        reminder_message = intent.data['message']
        logger.info(f"Creating reminder: '{reminder_message}' at {trigger_time}")

        # Add the reminder
        reminder_id = await reminders_service.add_reminder(
            user_id=message.author.id,
            channel_id=message.channel.id,
            message=reminder_message,
            trigger_time=trigger_time
        )

        logger.info(f"Reminder created with ID: {reminder_id}")

        if not reminder_id:
            max_reminders = Config.MAX_REMINDERS_PER_USER
            await message.channel.send(
                f"❌ You've reached the maximum of {max_reminders} reminders. "
                f"Use `/reminders` to see them or `/cancel_reminder` to remove some."
            )
            return True

        # Generate natural confirmation
        time_until = reminders_service.format_time_until(trigger_time)
        time_str = trigger_time.strftime("%I:%M %p")

        response = ConversationalResponder.generate_reminder_confirmation(
            reminder_message, time_str, time_until
        )

        await message.channel.send(response)
        logger.info(f"Created reminder via natural language: {reminder_message} in {time_until}")
        return True

    async def _handle_help_intent(self, message: discord.Message):
        """Handle help request intent."""
        embed = discord.Embed(
            title="💬 How to Talk to Me",
            description="You can talk to me naturally! Here are some things I understand:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="⏰ Reminders",
            value='Just say "remind me in 30 minutes to check the oven" or "remind me at 5pm to call mom"',
            inline=False
        )
        embed.add_field(
            name="💬 Chat",
            value="Mention me or just keep chatting in an active session! Ask me anything.",
            inline=False
        )
        embed.add_field(
            name="📋 Commands",
            value="Use `/chat`, `/remind`, `/speak`, and more! Type `/` to see all commands.",
            inline=False
        )

        await message.channel.send(embed=embed)

    async def _handle_time_intent(self, intent, message: discord.Message):
        """Handle time/date query intent."""
        try:
            from zoneinfo import ZoneInfo
            PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
        except ImportError:
            import pytz
            PACIFIC_TZ = pytz.timezone("America/Los_Angeles")

        now = datetime.now(PACIFIC_TZ)

        # Check if intent.data exists and has query_type
        query_type = intent.data.get('query_type', 'time') if intent.data else 'time'

        if query_type == 'time':
            time_str = now.strftime("%I:%M %p")
            responses = [
                f"It's {time_str}!",
                f"The time is {time_str}",
                f"{time_str} right now",
            ]
        else:
            date_str = now.strftime("%A, %B %d, %Y")
            responses = [
                f"It's {date_str}",
                f"Today is {date_str}",
                f"{date_str}!",
            ]

        await message.channel.send(random.choice(responses))

    async def _handle_trivia_intent(self, message: discord.Message) -> bool:
        """Handle trivia game intent."""
        trivia_service = getattr(self.bot, 'trivia_service', None)
        if trivia_service:
            await message.channel.send("Let's play trivia! Starting a game...")
            # Let the trivia cog handle it
            return False
        else:
            await message.channel.send("Trivia isn't enabled yet! Ask the admin to enable it.")
            return True

    async def _handle_custom_intent(self, intent, message: discord.Message) -> bool:
        """Handle custom server-specific intent."""
        custom_data = intent.data
        response_type = custom_data.get('response_type', 'text')

        if response_type == 'text' and custom_data.get('response_template'):
            # Simple text response
            response = custom_data['response_template']
            # Replace any capture groups
            if custom_data.get('groups'):
                for i, group in enumerate(custom_data['groups'], 1):
                    response = response.replace(f'{{{i}}}', group or '')

            await message.channel.send(response)
            return True

        elif response_type == 'embed':
            # Embed response
            embed = discord.Embed(
                title=custom_data.get('name', 'Custom Response'),
                description=custom_data.get('response_template', ''),
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)
            return True

        # If no response template, let AI handle it with context
        return False
