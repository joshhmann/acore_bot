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
    speaker: str
    content: str
    timestamp: datetime
    turn_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMetrics:
    character_consistency: float = 0.0
    turn_relevance: float = 0.0
    avg_latency: float = 0.0
    vocab_diversity: float = 0.0
    quality_score: float = 0.0


@dataclass
class ConversationState:
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
                    "metadata": m.metadata,
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
                "quality_score": self.metrics.quality_score,
            },
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationState":
        messages = [
            Message(
                speaker=m["speaker"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                turn_number=m["turn_number"],
                metadata=m.get("metadata", {}),
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
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else None,
            ended_at=datetime.fromisoformat(data["ended_at"])
            if data.get("ended_at")
            else None,
            termination_reason=data.get("termination_reason"),
            metrics=ConversationMetrics(**data.get("metrics", {})),
            metadata=data.get("metadata", {}),
        )
