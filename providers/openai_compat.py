from __future__ import annotations

import json
from typing import Any

import aiohttp

from .base import (
    LLMProvider,
    LLMResponse,
    LLMStreamChunk,
    ProviderMessage,
    ProviderRequestHints,
    ProviderToolCall,
    ProviderUsage,
)


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.available_models: list[str] = []
        self.timeout_seconds = timeout_seconds
        self._session: aiohttp.ClientSession | None = None

    async def _session_or_create(self) -> aiohttp.ClientSession:
        if self._session is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        request_hints: ProviderRequestHints | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        del request_hints
        model = str(kwargs.get("model_override") or self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    **({"name": m.name} if m.name else {}),
                    **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                }
                for m in messages
            ],
            "stream": stream,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        session = await self._session_or_create()
        url = f"{self.base_url}/chat/completions"
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    return LLMResponse(
                        content="",
                        tool_calls=[],
                        usage=ProviderUsage(),
                        raw={"error": f"status={resp.status}", "body": body},
                    )
                data = await resp.json()
        except Exception as exc:
            return LLMResponse(
                content="",
                tool_calls=[],
                usage=ProviderUsage(),
                raw={"error": str(exc)},
            )

        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(content="", usage=self._parse_usage(data), raw=data)

        message = choices[0].get("message") or {}
        content = str(message.get("content") or "")
        parsed_tool_calls: list[ProviderToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = (
                    json.loads(args_raw)
                    if isinstance(args_raw, str)
                    else dict(args_raw)
                )
            except Exception:
                args = {}
            parsed_tool_calls.append(
                ProviderToolCall(
                    name=str(fn.get("name") or ""),
                    arguments=args,
                    call_id=tc.get("id"),
                )
            )

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            usage=self._parse_usage(data),
            raw=data,
        )

    async def stream_chat(
        self,
        messages: list[ProviderMessage],
        tools: list[dict[str, Any]] | None = None,
        request_hints: ProviderRequestHints | None = None,
        **kwargs: Any,
    ):
        del request_hints
        model = str(kwargs.get("model_override") or self.model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    **({"name": m.name} if m.name else {}),
                    **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                }
                for m in messages
            ],
            "stream": True,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        session = await self._session_or_create()
        url = f"{self.base_url}/chat/completions"
        content_parts: list[str] = []
        tool_chunks: dict[int, dict[str, Any]] = {}
        usage = ProviderUsage()
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    response = LLMResponse(
                        content="",
                        tool_calls=[],
                        usage=ProviderUsage(),
                        raw={"error": f"status={resp.status}", "body": body},
                    )
                    yield LLMStreamChunk(kind="response", response=response, raw=dict(response.raw))
                    return
                while True:
                    raw_line = await resp.content.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        data = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    if data.get("usage"):
                        usage = self._parse_usage(data)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    text_delta = str(delta.get("content") or "")
                    if text_delta:
                        content_parts.append(text_delta)
                        yield LLMStreamChunk(
                            kind="text_delta",
                            text=text_delta,
                            raw=data,
                        )
                    for call in delta.get("tool_calls") or []:
                        index = int(call.get("index") or 0)
                        target = tool_chunks.setdefault(
                            index,
                            {"name": "", "arguments": "", "call_id": None},
                        )
                        if call.get("id"):
                            target["call_id"] = call.get("id")
                        fn = call.get("function") or {}
                        if fn.get("name"):
                            target["name"] = str(fn.get("name"))
                        if fn.get("arguments"):
                            target["arguments"] += str(fn.get("arguments"))
        except Exception as exc:
            response = LLMResponse(
                content="",
                tool_calls=[],
                usage=ProviderUsage(),
                raw={"error": str(exc)},
            )
            yield LLMStreamChunk(kind="response", response=response, raw=dict(response.raw))
            return

        parsed_tool_calls: list[ProviderToolCall] = []
        for item in tool_chunks.values():
            raw_arguments = str(item.get("arguments") or "{}")
            try:
                arguments = json.loads(raw_arguments) if raw_arguments else {}
            except Exception:
                arguments = {}
            parsed_tool_calls.append(
                ProviderToolCall(
                    name=str(item.get("name") or ""),
                    arguments=arguments,
                    call_id=item.get("call_id"),
                )
            )
        response = LLMResponse(
            content="".join(content_parts),
            tool_calls=parsed_tool_calls,
            usage=usage,
            raw={"streamed": True, "model": model},
        )
        yield LLMStreamChunk(kind="response", response=response, raw=dict(response.raw))

    @staticmethod
    def _parse_usage(payload: dict[str, Any]) -> ProviderUsage:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return ProviderUsage()
        prompt_details = usage.get("prompt_tokens_details")
        if not isinstance(prompt_details, dict):
            prompt_details = {}
        return ProviderUsage(
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            cached_input_tokens=int(prompt_details.get("cached_tokens") or 0),
        )
