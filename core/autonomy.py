from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from core.schemas import Event


class AutonomyRuntime(Protocol):
    async def handle_event(self, event: Event): ...


@dataclass(slots=True)
class AutonomyConfig:
    enabled: bool = False
    interval_seconds: float = 60.0
    action_probability: float = 0.1
    room_id: str = "autonomy"
    persona_id: str = "default"
    min_cooldown_seconds: float = 60.0
    user_activity_grace_seconds: float = 45.0
    token_budget_per_window: int = 600


@dataclass(slots=True)
class ShouldActGate:
    config: AutonomyConfig
    last_action_at: datetime | None = None
    last_user_activity_at: datetime | None = None
    token_budget_used: int = 0

    def record_user_activity(self, at: datetime | None = None) -> None:
        self.last_user_activity_at = at or datetime.now(timezone.utc)

    def can_act(self, now: datetime) -> bool:
        if self.last_action_at is not None:
            if (
                now - self.last_action_at
            ).total_seconds() < self.config.min_cooldown_seconds:
                return False
        if self.last_user_activity_at is not None:
            if (
                now - self.last_user_activity_at
            ).total_seconds() < self.config.user_activity_grace_seconds:
                return False
        if self.token_budget_used >= self.config.token_budget_per_window:
            return False
        return True

    def record_action(self, now: datetime, estimated_tokens: int) -> None:
        self.last_action_at = now
        self.token_budget_used += max(0, estimated_tokens)


class AutonomyScheduler:
    def __init__(self, runtime: AutonomyRuntime, config: AutonomyConfig) -> None:
        self.runtime = runtime
        self.config = config
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.gate = ShouldActGate(config=config)

    async def start(self) -> None:
        if not self.config.enabled or self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(max(1.0, self.config.interval_seconds))
            now = datetime.now(timezone.utc)
            if not self._should_act(now):
                continue
            event = Event(
                type="tick",
                text="",
                user_id="autonomy",
                room_id=self.config.room_id,
                platform="autonomy",
                message_id="",
                timestamp=datetime.now(timezone.utc),
                metadata={"persona_id": self.config.persona_id},
            )
            response = await self.runtime.handle_event(event)
            estimated_tokens = max(1, len(response.text) // 4) if response else 1
            self.gate.record_action(now=now, estimated_tokens=estimated_tokens)

    def _should_act(self, now: datetime) -> bool:
        if not self.gate.can_act(now=now):
            return False
        return random.random() < self.config.action_probability

    def record_user_activity(self, at: datetime | None = None) -> None:
        self.gate.record_user_activity(at=at)
