# Task 1 Implementation Guide: Conversation State Schema + Persistence

## Overview
Create the foundation for bot-to-bot conversation state management.

## Files to Create

### 1. `services/conversation/state.py`

```python
"""Conversation state management for bot-to-bot conversations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum


class ConversationStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Message:
    """A single message in a bot-to-bot conversation."""
    speaker: str  # Persona ID
    content: str
    timestamp: datetime
    turn_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMetrics:
    """Metrics for a bot-to-bot conversation."""
    character_consistency: float = 0.0
    turn_relevance: float = 0.0
    avg_latency: float = 0.0
    vocab_diversity: float = 0.0
    quality_score: float = 0.0


@dataclass
class ConversationState:
    """Complete state for a bot-to-bot conversation."""
    conversation_id: str
    participants: List[str]
    status: ConversationStatus
    turn_count: int = 0
    max_turns: int = 10
    messages: List[Message] = field(default_factory=list)
    current_speaker: Optional[str] = None
    topic: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    termination_reason: Optional[str] = None
    metrics: ConversationMetrics = field(default_factory=ConversationMetrics)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "participants": self.participants,
            "status": self.status.value,
            "turn_count": self.turn_count,
            "max_turns": self.max_turns,
            "messages": [
                {
                    "speaker": m.speaker,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "turn_number": m.turn_number,
                    "metadata": m.metadata
                }
                for m in self.messages
            ],
            "current_speaker": self.current_speaker,
            "topic": self.topic,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "termination_reason": self.termination_reason,
            "metrics": {
                "character_consistency": self.metrics.character_consistency,
                "turn_relevance": self.metrics.turn_relevance,
                "avg_latency": self.metrics.avg_latency,
                "vocab_diversity": self.metrics.vocab_diversity,
                "quality_score": self.metrics.quality_score
            },
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationState":
        """Create from dictionary."""
        messages = [
            Message(
                speaker=m["speaker"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                turn_number=m["turn_number"],
                metadata=m.get("metadata", {})
            )
            for m in data.get("messages", [])
        ]
        
        return cls(
            conversation_id=data["conversation_id"],
            participants=data["participants"],
            status=ConversationStatus(data["status"]),
            turn_count=data["turn_count"],
            max_turns=data.get("max_turns", 10),
            messages=messages,
            current_speaker=data.get("current_speaker"),
            topic=data.get("topic", ""),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            termination_reason=data.get("termination_reason"),
            metrics=ConversationMetrics(**data.get("metrics", {})),
            metadata=data.get("metadata", {})
        )
```

### 2. `services/conversation/persistence.py`

```python
"""Persistence layer for bot-to-bot conversation state."""

import json
import gzip
import aiofiles
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from services.conversation.state import ConversationState

logger = logging.getLogger(__name__)


class ConversationPersistence:
    """Handles saving and loading conversation state to/from disk."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_dir = self.base_dir / "active"
        self.archive_dir = self.base_dir / "archive"
        self.active_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
    
    def _get_file_path(self, conversation_id: str, archived: bool = False) -> Path:
        """Get the file path for a conversation."""
        dir_path = self.archive_dir if archived else self.active_dir
        return dir_path / f"{conversation_id}.jsonl"
    
    async def save(self, state: ConversationState) -> None:
        """Save conversation state atomically."""
        file_path = self._get_file_path(state.conversation_id)
        temp_path = file_path.with_suffix(".tmp")
        
        try:
            # Write to temp file first (atomic operation)
            async with aiofiles.open(temp_path, 'w') as f:
                await f.write(json.dumps(state.to_dict()) + "\n")
            
            # Atomic rename
            temp_path.replace(file_path)
            logger.debug(f"Saved conversation {state.conversation_id}")
            
        except Exception as e:
            logger.error(f"Failed to save conversation {state.conversation_id}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    async def load(self, conversation_id: str) -> Optional[ConversationState]:
        """Load conversation state from disk."""
        # Check active first, then archive
        for archived in [False, True]:
            file_path = self._get_file_path(conversation_id, archived)
            if file_path.exists():
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        data = json.loads(content.strip())
                        return ConversationState.from_dict(data)
                except Exception as e:
                    logger.error(f"Failed to load conversation {conversation_id}: {e}")
                    return None
        
        return None
    
    async def list_active(self) -> List[str]:
        """List all active conversation IDs."""
        return [f.stem for f in self.active_dir.glob("*.jsonl")]
    
    async def archive(self, conversation_id: str) -> bool:
        """Move conversation to archive (compress with gzip)."""
        active_path = self._get_file_path(conversation_id, archived=False)
        archive_path = self.archive_dir / f"{conversation_id}.jsonl.gz"
        
        if not active_path.exists():
            return False
        
        try:
            # Read active file
            async with aiofiles.open(active_path, 'rb') as f:
                content = await f.read()
            
            # Compress and write to archive
            async with aiofiles.open(archive_path, 'wb') as f:
                await f.write(gzip.compress(content))
            
            # Remove active file
            active_path.unlink()
            logger.info(f"Archived conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive conversation {conversation_id}: {e}")
            return False
    
    async def cleanup_old(self, max_age_days: int = 30) -> int:
        """Remove conversations older than max_age_days."""
        cutoff = datetime.now() - timedelta(days=max_age_days)
        removed = 0
        
        for file_path in self.archive_dir.glob("*.jsonl.gz"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    file_path.unlink()
                    removed += 1
                    logger.info(f"Cleaned up old conversation file: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to cleanup {file_path}: {e}")
        
        return removed
```

### 3. `tests/unit/test_conversation_state.py`

```python
"""Tests for conversation state management."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import asyncio

from services.conversation.state import (
    ConversationState, ConversationStatus, Message, ConversationMetrics
)
from services.conversation.persistence import ConversationPersistence


class TestConversationState:
    def test_message_creation(self):
        msg = Message(
            speaker="dagoth_ur",
            content="Welcome, mortal.",
            timestamp=datetime.now(),
            turn_number=1
        )
        assert msg.speaker == "dagoth_ur"
        assert msg.content == "Welcome, mortal."
    
    def test_state_serialization(self):
        state = ConversationState(
            conversation_id="test-123",
            participants=["dagoth_ur", "toad"],
            status=ConversationStatus.ACTIVE,
            turn_count=2,
            messages=[
                Message("dagoth_ur", "Hello", datetime.now(), 1),
                Message("toad", "Hi there!", datetime.now(), 2)
            ]
        )
        
        # Test to_dict
        data = state.to_dict()
        assert data["conversation_id"] == "test-123"
        assert len(data["messages"]) == 2
        
        # Test from_dict
        restored = ConversationState.from_dict(data)
        assert restored.conversation_id == "test-123"
        assert restored.turn_count == 2
        assert len(restored.messages) == 2


class TestConversationPersistence:
    @pytest.fixture
    async def persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ConversationPersistence(Path(tmpdir))
    
    @pytest.mark.asyncio
    async def test_save_and_load(self, persistence):
        state = ConversationState(
            conversation_id="test-save",
            participants=["bot1", "bot2"],
            status=ConversationStatus.COMPLETED,
            turn_count=5
        )
        
        # Save
        await persistence.save(state)
        
        # Load
        loaded = await persistence.load("test-save")
        assert loaded is not None
        assert loaded.conversation_id == "test-save"
        assert loaded.turn_count == 5
    
    @pytest.mark.asyncio
    async def test_list_active(self, persistence):
        # Create multiple conversations
        for i in range(3):
            state = ConversationState(
                conversation_id=f"conv-{i}",
                participants=["bot1", "bot2"],
                status=ConversationStatus.ACTIVE
            )
            await persistence.save(state)
        
        active = await persistence.list_active()
        assert len(active) == 3
        assert "conv-0" in active
```

## Testing Commands

```bash
# Run unit tests
uv run pytest tests/unit/test_conversation_state.py -v

# Run with coverage
uv run pytest tests/unit/test_conversation_state.py --cov=services.conversation -v
```

## Integration Points

- Used by `BotConversationOrchestrator` to maintain conversation state
- Persisted to `data/bot_conversations/` directory
- Supports atomic writes and recovery on startup
