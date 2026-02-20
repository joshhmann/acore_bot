"""Bot-to-Bot Conversation Orchestrator.

This is the core service that manages multi-turn conversations
between AI personas using events for output delivery.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional, Any

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
from core.interfaces import EventBus
from core.types import (
    PersonaSpokeEvent,
    ConversationTypingEvent,
    ConversationSummaryEvent,
)

logger = logging.getLogger(__name__)


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
        event_bus: Optional[EventBus] = None,
        rag_service: Optional[Any] = None,
        persistence: Optional[ConversationPersistence] = None,
        archival_service: Optional[ConversationArchivalService] = None,
    ):
        self.persona_router = persona_router
        self.behavior_engine = behavior_engine
        self.llm = llm_service
        self.event_bus = event_bus
        self.rag = rag_service
        self.persistence = persistence
        self.archival = archival_service

        self.active_conversations: Dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()

    async def start_conversation(
        self,
        participants: List[str],
        topic: str,
        channel_id: str,
        config: Optional[ConversationConfig] = None,
    ) -> str:
        """Start a new bot-to-bot conversation.

        Args:
            participants: List of persona IDs to participate
            topic: Conversation topic
            channel_id: Platform-agnostic channel identifier
            config: Optional conversation configuration

        Returns:
            conversation_id: Unique ID for this conversation
        """
        config = config or ConversationConfig()

        if config.seed is not None:
            random.seed(config.seed)

        conversation_id = f"conv-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{random.randint(1000, 9999)}"

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

        asyncio.create_task(self._run_conversation(state, channel_id, config))

        logger.info(
            f"Started conversation {conversation_id} with participants: {participants}"
        )
        return conversation_id

    async def _run_conversation(
        self,
        state: ConversationState,
        channel_id: str,
        config: ConversationConfig,
    ):
        """Run the conversation loop."""

        try:
            current_speaker = random.choice(state.participants)
            state.current_speaker = current_speaker

            await self._generate_and_send_message(
                state, current_speaker, channel_id, config, is_first=True
            )

            while state.turn_count < config.max_turns:
                if self._is_timeout(state, config.turn_timeout_seconds):
                    state.termination_reason = "timeout"
                    break

                next_speaker = self._select_next_speaker(state)
                if not next_speaker:
                    break

                state.current_speaker = next_speaker

                await self._emit_typing(channel_id)

                max_retries = 2
                success = False
                for attempt in range(max_retries):
                    success = await self._generate_and_send_message(
                        state, next_speaker, channel_id, config
                    )
                    if success:
                        break

                if not success:
                    logger.warning(
                        f"Retry attempts exhausted for {next_speaker}, continuing conversation..."
                    )

                    await self._emit_persona_spoke(
                        channel_id=channel_id,
                        conversation_id=state.conversation_id,
                        persona_id=next_speaker,
                        display_name=next_speaker,
                        avatar_url="",
                        content="[Message failed to generate - continuing conversation]",
                    )
                    continue

                await asyncio.sleep(1)

                if self._should_end_conversation(state):
                    state.termination_reason = "natural_end"
                    break

                await asyncio.sleep(random.uniform(3, 5))

            state.status = ConversationStatus.COMPLETED
            if not state.termination_reason:
                state.termination_reason = "turn_limit"

            state.ended_at = datetime.now()

            if config.enable_metrics:
                await self._calculate_metrics(state)
                await self._process_rl_feedback(state, config)

            if self.persistence:
                await self.persistence.save(state)

            if self.archival:
                try:
                    await self.archival.index_to_rag(state)
                except Exception as e:
                    logger.warning(f"Failed to index conversation to RAG: {e}")

            await self._send_summary(state, channel_id)

        except Exception as e:
            logger.error(f"Conversation {state.conversation_id} failed: {e}")
            state.status = ConversationStatus.FAILED
            state.termination_reason = f"error: {str(e)}"

        finally:
            async with self._lock:
                if state.conversation_id in self.active_conversations:
                    del self.active_conversations[state.conversation_id]

    async def _generate_and_send_message(
        self,
        state: ConversationState,
        speaker: str,
        channel_id: str,
        config: ConversationConfig,
        is_first: bool = False,
    ) -> bool:
        """Generate and send a message from a persona."""

        try:
            context = self._build_context(state, speaker, is_first)

            persona = self.persona_router.get_persona_by_name(speaker)
            if not persona:
                logger.error(f"Persona {speaker} not found")
                return False

            start_time = datetime.now()

            response = await self.llm.chat(
                messages=context,
                system_prompt=persona.system_prompt,
                temperature=0.8,
                max_tokens=150,
            )

            latency = (datetime.now() - start_time).total_seconds()

            message = Message(
                speaker=speaker,
                content=response,
                timestamp=datetime.now(),
                turn_number=state.turn_count + 1,
                metadata={"latency": latency},
            )

            state.messages.append(message)
            state.turn_count += 1

            avatar_val = getattr(persona.character, "avatar_url", None)
            avatar_url_val = str(avatar_val) if avatar_val is not None else ""
            from typing import cast

            avatar_url_arg = cast(str, avatar_url_val)

            await self._emit_persona_spoke(
                channel_id=channel_id,
                conversation_id=state.conversation_id,
                persona_id=speaker,
                display_name=persona.character.display_name,
                avatar_url=avatar_url_arg,
                content=response,
            )

            logger.debug(f"Sent message from {speaker}: {response[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to generate/send message: {e}")
            return False

    async def _emit_persona_spoke(
        self,
        channel_id: str,
        conversation_id: str,
        persona_id: str,
        display_name: str,
        avatar_url: str,
        content: str,
    ) -> None:
        """Emit a PersonaSpokeEvent to the event bus."""
        if self.event_bus:
            event = PersonaSpokeEvent(
                conversation_id=conversation_id,
                channel_id=channel_id,
                persona_id=persona_id,
                display_name=display_name,
                avatar_url=avatar_url,
                content=content,
            )
            self.event_bus.emit("persona_spoke", event.__dict__)

    async def _emit_typing(self, channel_id: str, duration_seconds: float = 1.0) -> None:
        """Emit a ConversationTypingEvent to the event bus."""
        if self.event_bus:
            event = ConversationTypingEvent(
                channel_id=channel_id,
                duration_seconds=duration_seconds,
            )
            self.event_bus.emit("conversation_typing", event.__dict__)

    def _build_context(
        self, state: ConversationState, speaker: str, is_first: bool
    ) -> List[Dict[str, str]]:
        """Build conversation context for LLM."""

        context = []

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

        for msg in state.messages[-5:]:
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

        others = [p for p in state.participants if p != current]
        if not others:
            return current

        weights = []
        for participant in others:
            affinity = self._get_affinity(current, participant)
            weight = affinity + random.randint(0, 20)
            weights.append(weight)

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

        farewells = ["goodbye", "farewell", "bye", "see you", "talk later"]
        if any(f in last_message for f in farewells):
            return True

        return False

    async def _calculate_metrics(self, state: ConversationState):
        """Calculate conversation quality metrics."""
        from config import Config

        calculator = ConversationMetricsCalculator(
            llm_service=self.llm,
            detailed_metrics=Config.BOT_CONVERSATION_DETAILED_METRICS,
        )

        state.metrics = await calculator.calculate_all_metrics(state)

    async def _process_rl_feedback(self, state: ConversationState, config: ConversationConfig) -> None:
        """Process reinforcement learning feedback for the conversation."""
        try:
            from config import Config as _Config
            import inspect

            if (
                getattr(_Config, "BOTCONV_RL_TRAINING_ENABLED", False)
                and hasattr(self, "behavior_engine")
                and self.behavior_engine
                and hasattr(self.behavior_engine, "rl_service")
                and self.behavior_engine.rl_service
            ):
                engagement = None
                metrics = getattr(state, "metrics", None)
                if metrics is not None:
                    engagement = getattr(metrics, "engagement", None)
                score = 0.0
                if engagement is not None:
                    if engagement > 0.7:
                        score = 0.9
                    elif engagement > 0.4:
                        score = 0.6
                    else:
                        score = 0.3

                state_info = {
                    "conversation_id": getattr(state, "conversation_id", None),
                    "turns": getattr(state, "turn_count", None),
                    "participants": getattr(state, "participants", []),
                }

                reward = 1.0 if score > 0.6 else (-1.0 if score < 0.4 else 0.0)
                if reward != 0.0:
                    rl_service = self.behavior_engine.rl_service
                    record_feedback = getattr(
                        rl_service, "record_feedback", None
                    )
                    if record_feedback:
                        try:
                            if inspect.iscoroutinefunction(record_feedback):
                                await record_feedback(state_info, reward)
                            else:
                                record_feedback(state_info, reward)
                        except Exception as e:
                            logger.debug(f"RL record_feedback call failed: {e}")
        except Exception as e:
            logger.debug(f"RL training integration skip: {e}")

    async def _send_summary(
        self,
        state: ConversationState,
        channel_id: str,
    ):
        """Send conversation summary via event."""

        avg_latency = state.metrics.avg_latency if state.metrics else 0.0

        if self.event_bus:
            event = ConversationSummaryEvent(
                conversation_id=state.conversation_id,
                channel_id=channel_id,
                participants=state.participants,
                topic=state.topic,
                turn_count=state.turn_count,
                max_turns=state.max_turns,
                termination_reason=state.termination_reason or "unknown",
                avg_latency=avg_latency,
            )
            self.event_bus.emit("conversation_summary", event.__dict__)

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
