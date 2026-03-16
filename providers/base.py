from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass(slots=True)
class ProviderMessage:
    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass(slots=True)
class ProviderToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(slots=True)
class LLMResponse:
    content: str
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMStreamChunk:
    kind: str
    text: str = ""
    response: LLMResponse | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse: ...

    async def stream_chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMStreamChunk]: ...
