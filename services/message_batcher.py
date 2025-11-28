"""AI-powered message batching service."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import discord

logger = logging.getLogger(__name__)


class MessageBatcher:
    """Intelligently batches messages using AI to decide when to respond."""

    def __init__(self, bot, ollama_service):
        """Initialize message batcher.
        
        Args:
            bot: Discord bot instance
            ollama_service: Ollama service for AI decisions
        """
        self.bot = bot
        self.ollama = ollama_service
        self.pending_messages: Dict[tuple, List[discord.Message]] = {}  # (channel_id, user_id) -> messages
        self.timers: Dict[tuple, asyncio.Task] = {}  # (channel_id, user_id) -> timer task
        self.max_wait_time = 4.0  # Maximum seconds to wait before forcing response
        self.min_wait_time = 1.5  # Minimum seconds to wait before checking
        
    async def add_message(self, message: discord.Message, response_callback) -> bool:
        """Add a message to the batch and decide whether to respond.
        
        Args:
            message: Discord message to add
            response_callback: Async function to call when ready to respond
            
        Returns:
            True if message was batched, False if should respond immediately
        """
        key = (message.channel.id, message.author.id)
        
        # Initialize pending messages for this user
        if key not in self.pending_messages:
            self.pending_messages[key] = []
        
        # Add message to pending
        self.pending_messages[key].append(message)
        
        # Cancel existing timer if any
        if key in self.timers:
            self.timers[key].cancel()
        
        # Start new timer
        timer = asyncio.create_task(
            self._wait_and_decide(key, response_callback)
        )
        self.timers[key] = timer
        
        return True  # Message was batched
    
    async def _wait_and_decide(self, key: tuple, response_callback):
        """Wait minimum time, then ask AI if we should respond or wait longer.
        
        Args:
            key: (channel_id, user_id) tuple
            response_callback: Function to call when ready to respond
        """
        try:
            # Wait minimum time
            await asyncio.sleep(self.min_wait_time)
            
            # Get pending messages
            messages = self.pending_messages.get(key, [])
            if not messages:
                return
            
            # Ask AI if we should respond now
            should_respond = await self._ask_ai_if_ready(messages)
            
            if should_respond:
                # Respond immediately
                await self._process_batch(key, response_callback)
            else:
                # Wait a bit longer, but not forever
                remaining_wait = self.max_wait_time - self.min_wait_time
                await asyncio.sleep(remaining_wait)
                
                # Force response after max wait time
                await self._process_batch(key, response_callback)
                
        except asyncio.CancelledError:
            # Timer was cancelled (new message arrived)
            pass
        except Exception as e:
            logger.error(f"Error in message batching: {e}")
            # On error, process immediately
            await self._process_batch(key, response_callback)
    
    async def _ask_ai_if_ready(self, messages: List[discord.Message]) -> bool:
        """Ask AI if the messages seem complete or if user might send more.
        
        Args:
            messages: List of pending messages
            
        Returns:
            True if should respond now, False if should wait
        """
        try:
            # Combine messages
            combined = "\n".join([f"- {m.content}" for m in messages])
            
            prompt = f"""User sent these messages in quick succession:
{combined}

Do these messages seem COMPLETE (ready for a response), or does it seem like the user might send more messages to finish their thought?

Consider:
- Are they asking a complete question?
- Did they finish their sentence/thought?
- Is this a natural stopping point?

Answer ONLY "complete" or "incomplete"."""

            response = await self.ollama.generate(prompt)
            
            is_complete = "complete" in response.lower() and "incomplete" not in response.lower()
            
            logger.debug(f"AI batching decision: {'respond now' if is_complete else 'wait for more'} (messages: {len(messages)})")
            
            return is_complete
            
        except Exception as e:
            logger.error(f"AI batching decision failed: {e}")
            # On error, assume complete (respond now)
            return True
    
    async def _process_batch(self, key: tuple, response_callback):
        """Process batched messages and respond.
        
        Args:
            key: (channel_id, user_id) tuple
            response_callback: Function to call with combined message
        """
        messages = self.pending_messages.get(key, [])
        if not messages:
            return
        
        try:
            # Combine messages into one
            combined_content = "\n".join([m.content for m in messages])
            
            # Use the last message as the context (has most recent timestamp, etc)
            last_message = messages[-1]
            
            # Create a pseudo-message with combined content
            # We'll pass both the combined content and original message
            logger.info(f"Processing batch of {len(messages)} messages: {combined_content[:100]}...")
            
            # Call the response callback with combined content
            await response_callback(combined_content, last_message)
            
        finally:
            # Clean up
            if key in self.pending_messages:
                del self.pending_messages[key]
            if key in self.timers:
                del self.timers[key]
    
    def cancel_batch(self, channel_id: int, user_id: int):
        """Cancel pending batch for a user.
        
        Args:
            channel_id: Channel ID
            user_id: User ID
        """
        key = (channel_id, user_id)
        
        if key in self.timers:
            self.timers[key].cancel()
            del self.timers[key]
        
        if key in self.pending_messages:
            del self.pending_messages[key]
    
    def has_pending(self, channel_id: int, user_id: int) -> bool:
        """Check if user has pending messages.
        
        Args:
            channel_id: Channel ID
            user_id: User ID
            
        Returns:
            True if user has pending messages
        """
        key = (channel_id, user_id)
        return key in self.pending_messages and len(self.pending_messages[key]) > 0
