# Task 4 Implementation Guide: BotConversationOrchestrator (CORE)

## Overview
This is the **heart of the system** - the orchestrator that manages bot-to-bot conversations. This is the most complex task (50% of implementation effort).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 BotConversationOrchestrator                 │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Conversation │  │   Turn       │  │   Webhook    │      │
│  │   State      │  │  Manager     │  │    Pool      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  Dependencies: PersonaRouter, BehaviorEngine, LLM, RAG     │
└─────────────────────────────────────────────────────────────┘
```

## Files to Create

### 1. `services/conversation/orchestrator.py`

```python
"""Bot-to-Bot Conversation Orchestrator.

This is the core service that manages multi-turn conversations
between AI personas using webhooks for persona spoofing.
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import discord

from services.conversation.state import (
    ConversationState, ConversationStatus, Message, ConversationMetrics
)
from services.conversation.persistence import ConversationPersistence
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
        self, 
        persona_id: str, 
        display_name: str, 
        avatar_url: str
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
            await old_webhook.edit(name=display_name, avatar=avatar_url)
            self.webhooks[persona_id] = old_webhook
            self.webhook_order.append(persona_id)
            return old_webhook
        
        # Create new webhook
        try:
            webhook = await self.channel.create_webhook(
                name=display_name,
                avatar=avatar_url
            )
            self.webhooks[persona_id] = webhook
            self.webhook_order.append(persona_id)
            logger.debug(f"Created webhook for {persona_id}")
            return webhook
        except discord.HTTPException as e:
            logger.error(f"Failed to create webhook: {e}")
            raise


@dataclass
class ConversationConfig:
    """Configuration for a bot-to-bot conversation."""
    max_turns: int = 10
    turn_timeout_seconds: int = 60
    enable_tools: bool = False
    enable_metrics: bool = False
    seed: Optional[int] = None


class BotConversationOrchestrator:
    """Orchestrates bot-to-bot conversations."""
    
    def __init__(
        self,
        persona_router: PersonaRouter,
        behavior_engine: BehaviorEngine,
        llm_service: Any,
        rag_service: Optional[Any] = None,
        persistence: Optional[ConversationPersistence] = None
    ):
        self.persona_router = persona_router
        self.behavior_engine = behavior_engine
        self.llm = llm_service
        self.rag = rag_service
        self.persistence = persistence
        
        self.active_conversations: Dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()
    
    async def start_conversation(
        self,
        participants: List[str],
        topic: str,
        channel: discord.TextChannel,
        config: Optional[ConversationConfig] = None
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
            started_at=datetime.now()
        )
        
        async with self._lock:
            self.active_conversations[conversation_id] = state
        
        # Start conversation in background
        asyncio.create_task(
            self._run_conversation(state, channel, config)
        )
        
        logger.info(f"Started conversation {conversation_id} with participants: {participants}")
        return conversation_id
    
    async def _run_conversation(
        self,
        state: ConversationState,
        channel: discord.TextChannel,
        config: ConversationConfig
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
        is_first: bool = False
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
                system_prompt=persona.system_prompt,
                messages=context,
                temperature=0.8
            )
            
            latency = (datetime.now() - start_time).total_seconds()
            
            # Create message object
            message = Message(
                speaker=speaker,
                content=response,
                timestamp=datetime.now(),
                turn_number=state.turn_count + 1,
                metadata={"latency": latency}
            )
            
            state.messages.append(message)
            state.turn_count += 1
            
            # Send via webhook
            webhook = await webhook_pool.get_or_create_webhook(
                speaker,
                persona.display_name,
                persona.avatar_url
            )
            
            # Attach conversation metadata for loop prevention bypass
            sent_message = await webhook.send(
                content=response,
                username=persona.display_name,
                avatar_url=persona.avatar_url,
                wait=True
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
        self, 
        state: ConversationState, 
        speaker: str,
        is_first: bool
    ) -> List[Dict[str, str]]:
        """Build conversation context for LLM."""
        
        context = []
        
        # Add system instruction
        if is_first:
            context.append({
                "role": "system",
                "content": f"Start a conversation about: {state.topic}. Introduce yourself and engage naturally."
            })
        else:
            context.append({
                "role": "system",
                "content": f"Continue the conversation about: {state.topic}. Respond to the previous message naturally."
            })
        
        # Add conversation history
        for msg in state.messages[-5:]:  # Last 5 messages for context
            context.append({
                "role": "assistant" if msg.speaker == speaker else "user",
                "content": f"{msg.speaker}: {msg.content}"
            })
        
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
        # TODO: Implement detailed metrics
        state.metrics.avg_latency = sum(
            m.metadata.get("latency", 0) for m in state.messages
        ) / len(state.messages) if state.messages else 0
    
    async def _send_summary(
        self, 
        state: ConversationState, 
        channel: discord.TextChannel,
        webhook_pool: WebhookPool
    ):
        """Send conversation summary."""
        
        summary = f"""
**Conversation Complete** ({state.conversation_id})
- Participants: {', '.join(state.participants)}
- Topic: {state.topic}
- Turns: {state.turn_count}/{state.max_turns}
- Duration: {(state.ended_at - state.started_at).total_seconds():.1f}s
- Ending: {state.termination_reason}
- Avg Latency: {state.metrics.avg_latency:.2f}s
        """.strip()
        
        await channel.send(summary)
    
    async def get_conversation(self, conversation_id: str) -> Optional[ConversationState]:
        """Get active conversation by ID."""
        async with self._lock:
            return self.active_conversations.get(conversation_id)
    
    async def list_active_conversations(self) -> List[str]:
        """List all active conversation IDs."""
        async with self._lock:
            return list(self.active_conversations.keys())
```

### 2. Update `services/core/factory.py`

```python
# Add to ServiceFactory class

def _init_conversation_system(self):
    """Initialize bot-to-bot conversation system."""
    from services.conversation.orchestrator import BotConversationOrchestrator
    from services.conversation.persistence import ConversationPersistence
    from config import Config
    
    # Initialize persistence
    persistence = ConversationPersistence(
        Config.DATA_DIR / "bot_conversations"
    )
    
    # Initialize orchestrator
    orchestrator = BotConversationOrchestrator(
        persona_router=self.services["persona_router"],
        behavior_engine=self.services["behavior_engine"],
        llm_service=self.services["ollama"],
        rag_service=self.services.get("rag"),
        persistence=persistence
    )
    
    self.services["conversation_orchestrator"] = orchestrator
    self.services["conversation_persistence"] = persistence
```

### 3. `tests/unit/test_orchestrator.py`

```python
"""Tests for BotConversationOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from services.conversation.orchestrator import (
    BotConversationOrchestrator, WebhookPool, ConversationConfig
)
from services.conversation.state import ConversationStatus


class TestWebhookPool:
    @pytest.mark.asyncio
    async def test_get_or_create_webhook(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.create_webhook = AsyncMock(return_value=MagicMock(
            name="TestWebhook", id=12345
        ))
        
        pool = WebhookPool(channel, max_webhooks=10)
        
        webhook = await pool.get_or_create_webhook(
            "persona1", "Persona 1", "http://avatar.png"
        )
        
        assert webhook is not None
        channel.create_webhook.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_reuse(self):
        channel = MagicMock(spec=discord.TextChannel)
        mock_webhook = MagicMock(name="TestWebhook", id=12345)
        channel.create_webhook = AsyncMock(return_value=mock_webhook)
        
        pool = WebhookPool(channel, max_webhooks=10)
        
        # First call creates webhook
        webhook1 = await pool.get_or_create_webhook(
            "persona1", "Persona 1", "http://avatar.png"
        )
        
        # Second call reuses webhook
        webhook2 = await pool.get_or_create_webhook(
            "persona1", "Persona 1", "http://avatar.png"
        )
        
        assert webhook1 == webhook2
        channel.create_webhook.assert_called_once()


class TestBotConversationOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        router = MagicMock()
        behavior = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="Test response")
        
        return BotConversationOrchestrator(router, behavior, llm)
    
    @pytest.mark.asyncio
    async def test_start_conversation(self, orchestrator):
        channel = MagicMock(spec=discord.TextChannel)
        channel.create_webhook = AsyncMock(return_value=MagicMock(
            send=AsyncMock(return_value=MagicMock())
        ))
        
        # Mock persona
        persona = MagicMock()
        persona.display_name = "TestPersona"
        persona.avatar_url = "http://avatar.png"
        persona.system_prompt = "You are a test persona"
        orchestrator.persona_router.get_persona = MagicMock(return_value=persona)
        
        config = ConversationConfig(max_turns=2, seed=42)
        
        conv_id = await orchestrator.start_conversation(
            participants=["bot1", "bot2"],
            topic="testing",
            channel=channel,
            config=config
        )
        
        assert conv_id is not None
        assert conv_id.startswith("conv-")
    
    @pytest.mark.asyncio
    async def test_select_next_speaker(self, orchestrator):
        from services.conversation.state import ConversationState
        
        state = ConversationState(
            conversation_id="test",
            participants=["bot1", "bot2", "bot3"],
            status=ConversationStatus.ACTIVE
        )
        state.current_speaker = "bot1"
        
        next_speaker = orchestrator._select_next_speaker(state)
        
        assert next_speaker in ["bot2", "bot3"]
        assert next_speaker != "bot1"
```

## Key Implementation Notes

### Webhook Pooling Strategy
- Max 10 webhooks per guild (Discord limit)
- LRU eviction when limit reached
- Reuse webhooks by updating name/avatar

### Turn Selection
- Affinity-weighted (default)
- Random fallback
- Prevents same speaker twice in a row

### Error Handling
- Graceful degradation on LLM failure
- Timeout protection
- State persistence on error

### Testing
- Use mocks for Discord objects
- Seed random for determinism
- Test webhook pooling logic

## Verification

```bash
# Run orchestrator tests
uv run pytest tests/unit/test_orchestrator.py -v

# Run with coverage
uv run pytest tests/unit/test_orchestrator.py --cov=services.conversation -v
```
