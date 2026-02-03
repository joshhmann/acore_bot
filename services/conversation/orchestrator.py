"""Bot-to-Bot Conversation Orchestrator.

This is the core service that manages multi-turn conversations
between AI personas using webhooks for persona spoofing.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional, Any

import discord

from services.conversation.state import (
    ConversationState,
    ConversationStatus,
    Message,
    ConversationMetrics,
)
from services.conversation.persistence import ConversationPersistence
from services.conversation.metrics import ConversationMetricsCalculator
from services.conversation.archival import ConversationArchivalService
from services.persona.router import PersonaRouter
from services.persona.behavior import BehaviorEngine

logger = logging.getLogger(__name__)


class WebhookPool:
    """Manages Discord webhooks to avoid rate limits.

    Discord limits: 10 webhooks per guild, 30 requests/minute per webhook.
    """

    def __init__(self, channel: discord.TextChannel, max_webhooks: int = 10):
        self.channel = channel
        self.max_webhooks = max_webhooks
        self.webhooks: Dict[str, discord.Webhook] = {}
        self.webhook_order: List[str] = []  # For LRU eviction

    async def get_or_create_webhook(
        self, persona_id: str, display_name: str, avatar_url: str
    ) -> discord.Webhook:
        """Get existing webhook or create new one."""

        if persona_id in self.webhooks:
            # Move to end (most recently used)
            self.webhook_order.remove(persona_id)
            self.webhook_order.append(persona_id)
            return self.webhooks[persona_id]

        # Check if we need to evict
        if len(self.webhooks) >= self.max_webhooks:
            # Evict least recently used
            lru_persona = self.webhook_order.pop(0)
            old_webhook = self.webhooks.pop(lru_persona)
            # Update webhook for new persona
            await old_webhook.edit(
                name=display_name, avatar=await self._fetch_avatar(avatar_url)
            )
            self.webhooks[persona_id] = old_webhook
            self.webhook_order.append(persona_id)
            return old_webhook

        # Create new webhook
        try:
            webhook = await self.channel.create_webhook(
                name=display_name, avatar=await self._fetch_avatar(avatar_url)
            )
            self.webhooks[persona_id] = webhook
            self.webhook_order.append(persona_id)
            logger.debug(f"Created webhook for {persona_id}")
            return webhook
        except discord.HTTPException as e:
            logger.error(f"Failed to create webhook: {e}")
            raise

    async def _fetch_avatar(self, avatar_url: str) -> Optional[bytes]:
        """Fetch avatar image bytes from URL."""
        if not avatar_url:
            return None

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.warning(f"Failed to fetch avatar from {avatar_url}: {e}")

        return None


class ConversationConfig:
    """Configuration for a bot-to-bot conversation."""

    def __init__(
        self,
        max_turns: int = 10,
        turn_timeout_seconds: int = 60,
        enable_tools: bool = False,
        enable_metrics: bool = False,
        seed: Optional[int] = None,
    ):
        self.max_turns = max_turns
        self.turn_timeout_seconds = turn_timeout_seconds
        self.enable_tools = enable_tools
        self.enable_metrics = enable_metrics
        self.seed = seed


class BotConversationOrchestrator:
    """Orchestrates bot-to-bot conversations."""

    def __init__(
        self,
        persona_router: PersonaRouter,
        behavior_engine: BehaviorEngine,
        llm_service: Any,
        rag_service: Optional[Any] = None,
        persistence: Optional[ConversationPersistence] = None,
        archival_service: Optional[ConversationArchivalService] = None,
    ):
        self.persona_router = persona_router
        self.behavior_engine = behavior_engine
        self.llm = llm_service
        self.rag = rag_service
        self.persistence = persistence
        self.archival = archival_service

        self.active_conversations: Dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()

    async def start_conversation(
        self,
        participants: List[str],
        topic: str,
        channel: discord.TextChannel,
        config: Optional[ConversationConfig] = None,
    ) -> str:
        """Start a new bot-to-bot conversation.

        Args:
            participants: List of persona IDs to participate
            topic: Conversation topic
            channel: Discord channel to post messages
            config: Optional conversation configuration

        Returns:
            conversation_id: Unique ID for this conversation
        """
        config = config or ConversationConfig()

        # Set random seed for reproducibility (if provided)
        if config.seed is not None:
            random.seed(config.seed)

        conversation_id = f"conv-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{random.randint(1000, 9999)}"

        # Create conversation state
        state = ConversationState(
            conversation_id=conversation_id,
            participants=participants,
            status=ConversationStatus.ACTIVE,
            topic=topic,
            max_turns=config.max_turns,
            started_at=datetime.now(),
        )

        async with self._lock:
            self.active_conversations[conversation_id] = state

        # Start conversation in background
        asyncio.create_task(self._run_conversation(state, channel, config))

        logger.info(
            f"Started conversation {conversation_id} with participants: {participants}"
        )
        return conversation_id

    async def _run_conversation(
        self,
        state: ConversationState,
        channel: discord.TextChannel,
        config: ConversationConfig,
    ):
        """Run the conversation loop."""

        webhook_pool = WebhookPool(channel)

        try:
            # Select initiator
            current_speaker = random.choice(state.participants)
            state.current_speaker = current_speaker

            # Generate initial message
            await self._generate_and_send_message(
                state, current_speaker, channel, webhook_pool, is_first=True
            )

            # Conversation loop
            while state.turn_count < config.max_turns:
                # Check for timeout
                if self._is_timeout(state, config.turn_timeout_seconds):
                    state.termination_reason = "timeout"
                    break

                # Select next speaker
                next_speaker = self._select_next_speaker(state)
                if not next_speaker:
                    break

                state.current_speaker = next_speaker

                # Generate and send message
                success = await self._generate_and_send_message(
                    state, next_speaker, channel, webhook_pool
                )

                if not success:
                    logger.warning(f"Failed to generate message for {next_speaker}")
                    continue

                # Check for natural ending
                if self._should_end_conversation(state):
                    state.termination_reason = "natural_end"
                    break

                # Small delay between messages for realism
                await asyncio.sleep(1)

            # Conversation complete
            state.status = ConversationStatus.COMPLETED
            if not state.termination_reason:
                state.termination_reason = "turn_limit"

            state.ended_at = datetime.now()

            # Calculate metrics
            if config.enable_metrics:
                await self._calculate_metrics(state)

            # Save state
            if self.persistence:
                await self.persistence.save(state)

            if self.archival:
                try:
                    await self.archival.index_to_rag(state)
                except Exception as e:
                    logger.warning(f"Failed to index conversation to RAG: {e}")

            # Send summary
            await self._send_summary(state, channel, webhook_pool)

        except Exception as e:
            logger.error(f"Conversation {state.conversation_id} failed: {e}")
            state.status = ConversationStatus.FAILED
            state.termination_reason = f"error: {str(e)}"

        finally:
            async with self._lock:
                del self.active_conversations[state.conversation_id]

    async def _generate_and_send_message(
        self,
        state: ConversationState,
        speaker: str,
        channel: discord.TextChannel,
        webhook_pool: WebhookPool,
        is_first: bool = False,
    ) -> bool:
        """Generate and send a message from a persona."""

        try:
            # Build context
            context = self._build_context(state, speaker, is_first)

            # Get persona details
            persona = self.persona_router.get_persona(speaker)
            if not persona:
                logger.error(f"Persona {speaker} not found")
                return False

            # Generate message via LLM
            start_time = datetime.now()

            response = await self.llm.generate(
                system_prompt=persona.system_prompt, messages=context, temperature=0.8
            )

            latency = (datetime.now() - start_time).total_seconds()

            # Create message object
            message = Message(
                speaker=speaker,
                content=response,
                timestamp=datetime.now(),
                turn_number=state.turn_count + 1,
                metadata={"latency": latency},
            )

            state.messages.append(message)
            state.turn_count += 1

            # Send via webhook
            webhook = await webhook_pool.get_or_create_webhook(
                speaker, persona.character.display_name, persona.character.avatar_url
            )

            # Attach conversation metadata for loop prevention bypass
            sent_message = await webhook.send(
                content=response,
                username=persona.character.display_name,
                avatar_url=persona.character.avatar_url,
                wait=True,
            )

            # Mark message as part of conversation (for loop prevention bypass)
            if sent_message:
                sent_message._bot_conversation_id = state.conversation_id

            logger.debug(f"Sent message from {speaker}: {response[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to generate/send message: {e}")
            return False

    def _build_context(
        self, state: ConversationState, speaker: str, is_first: bool
    ) -> List[Dict[str, str]]:
        """Build conversation context for LLM."""

        context = []

        # Add system instruction
        if is_first:
            context.append(
                {
                    "role": "system",
                    "content": f"Start a conversation about: {state.topic}. Introduce yourself and engage naturally.",
                }
            )
        else:
            context.append(
                {
                    "role": "system",
                    "content": f"Continue the conversation about: {state.topic}. Respond to the previous message naturally.",
                }
            )

        # Add conversation history
        for msg in state.messages[-5:]:  # Last 5 messages for context
            context.append(
                {
                    "role": "assistant" if msg.speaker == speaker else "user",
                    "content": f"{msg.speaker}: {msg.content}",
                }
            )

        return context

    def _select_next_speaker(self, state: ConversationState) -> Optional[str]:
        """Select the next speaker based on affinity-weighted strategy."""

        current = state.current_speaker
        if not current:
            return random.choice(state.participants)

        # Get other participants
        others = [p for p in state.participants if p != current]
        if not others:
            return current

        # Affinity-weighted selection
        weights = []
        for participant in others:
            # Get affinity from relationship system
            affinity = self._get_affinity(current, participant)
            # Add some randomness
            weight = affinity + random.randint(0, 20)
            weights.append(weight)

        # Weighted random choice
        total = sum(weights)
        if total == 0:
            return random.choice(others)

        r = random.uniform(0, total)
        cumulative = 0
        for participant, weight in zip(others, weights):
            cumulative += weight
            if r <= cumulative:
                return participant

        return others[-1]

    def _get_affinity(self, persona1: str, persona2: str) -> int:
        """Get affinity score between two personas."""
        # TODO: Integrate with PersonaRelationships service
        # For now, return default affinity
        return 50

    def _is_timeout(self, state: ConversationState, timeout_seconds: int) -> bool:
        """Check if conversation has timed out."""
        if not state.messages:
            return False

        last_message_time = state.messages[-1].timestamp
        elapsed = (datetime.now() - last_message_time).total_seconds()
        return elapsed > timeout_seconds

    def _should_end_conversation(self, state: ConversationState) -> bool:
        """Check if conversation should naturally end."""
        if not state.messages:
            return False

        last_message = state.messages[-1].content.lower()

        # Check for farewell keywords
        farewells = ["goodbye", "farewell", "bye", "see you", "talk later"]
        if any(f in last_message for f in farewells):
            return True

        # Check for question marks (if no response needed)
        if "?" not in last_message and state.turn_count >= 8:
            # Soft ending possible
            pass

        return False

    async def _calculate_metrics(self, state: ConversationState):
        """Calculate conversation quality metrics."""
        from config import Config

        calculator = ConversationMetricsCalculator(
            llm_service=self.llm,
            detailed_metrics=Config.BOT_CONVERSATION_DETAILED_METRICS,
        )

        state.metrics = await calculator.calculate_all_metrics(state)

    async def _send_summary(
        self,
        state: ConversationState,
        channel: discord.TextChannel,
        webhook_pool: WebhookPool,
    ):
        """Send conversation summary."""

        summary = f"""
**Conversation Complete** ({state.conversation_id})
- Participants: {", ".join(state.participants)}
- Topic: {state.topic}
- Turns: {state.turn_count}/{state.max_turns}
- Duration: {(state.ended_at - state.started_at).total_seconds():.1f}s
- Ending: {state.termination_reason}
- Avg Latency: {state.metrics.avg_latency:.2f}s
        """.strip()

        await channel.send(summary)

    async def get_conversation(
        self, conversation_id: str
    ) -> Optional[ConversationState]:
        """Get active conversation by ID."""
        async with self._lock:
            return self.active_conversations.get(conversation_id)

    async def list_active_conversations(self) -> List[str]:
        """List all active conversation IDs."""
        async with self._lock:
            return list(self.active_conversations.keys())
