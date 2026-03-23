from __future__ import annotations

import asyncio
import difflib
import os
import subprocess
import hashlib
import inspect
from dataclasses import dataclass, field
import json
from time import perf_counter
from datetime import datetime, timedelta, timezone
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from config import Config
from core.auth import AuthStore
from core.commands import CommandRegistry
from core.schemas import (
    ErrorOutput,
    Event,
    EventKind,
    Response,
    ResponseEnvelope,
    StateMutation,
    StructuredOutput,
    TextOutput,
    ToolCall,
    ToolResult,
    TraceOutput,
    VoiceOutputIntent,
)
from memory.base import MemoryNamespace
from memory.coordinator import MemoryCoordinator
from memory.manager import MemoryContextBundle, MemoryManager
from memory.rag import RAGStore
from memory.types import ActionRecord, Fact, ShortTermTurn, TypedMemoryContext
from memory.summary import DeterministicSummary
from personas.loader import PersonaCatalog, PersonaDefinition
from providers.base import ProviderMessage, ProviderRequestHints, ProviderUsage
from providers.router import ProviderRouter
from providers.registry import canonical_provider_name
from tools.mcp_source import MCPToolSource
from tools.policy import ToolPolicy
from tools.runner import ToolRunner

from .persona_engine import PersonaEngine
from .router import Router
from .trace import TraceEmitter


@dataclass(slots=True)
class RuntimeSessionState:
    session_id: str
    persona_id: str
    mode: str
    flags: dict[str, Any] = field(default_factory=dict)
    last_tool_calls_used: int = 0
    trace_spans: list[TraceOutput] = field(default_factory=list)
    autopilot_plan: list[str] = field(default_factory=list)
    autopilot_index: int = 0
    autopilot_active: bool = False
    autopilot_last_decision: str = ""
    yolo_enabled: bool = False
    provider_override: str = ""
    model_override: str = ""
    pending_diffs: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_tool_approvals: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_action_records: list[ActionRecord] = field(default_factory=list)
    last_provider_at: datetime | None = None
    last_tool_at: datetime | None = None
    last_response_at: datetime | None = None
    last_error_at: datetime | None = None
    last_persona_text: str = ""
    context_budget: "ContextBudget | None" = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_input_tokens: int = 0
    last_context_cache_key: str = ""
    last_context_cache_hit: bool = False
    last_context_cache_reason: str = ""
    last_context_memory_revision: str = ""


@dataclass(slots=True)
class ContextCacheEntry:
    """Cached stable prompt prefix for a runtime session/persona/mode/provider."""

    cache_key: str
    session_id: str
    persona_id: str
    mode: str
    provider_name: str
    model_name: str
    tool_manifest_digest: str
    signature: str
    stable_prefix_messages: list[dict[str, str]]
    context_tokens_estimate: int
    created_at: datetime
    last_used_at: datetime
    hit_count: int = 0


@dataclass
class ContextBudget:
    """Tracks token/cost budget for a session with per-provider cost tracking."""

    max_tokens: int = 0
    used_tokens: int = 0
    max_cost_usd: float = 0.0
    used_cost_usd: float = 0.0
    provider_costs: dict[str, dict[str, float]] = field(default_factory=dict)
    alert_thresholds: list[float] = field(default_factory=lambda: [0.5, 0.75, 0.9])
    triggered_alerts: set[float] = field(default_factory=set)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def remaining_cost(self) -> float:
        return max(0.0, self.max_cost_usd - self.used_cost_usd)

    @property
    def token_utilization(self) -> float:
        if self.max_tokens <= 0:
            return 0.0
        return self.used_tokens / self.max_tokens

    @property
    def cost_utilization(self) -> float:
        if self.max_cost_usd <= 0:
            return 0.0
        return self.used_cost_usd / self.max_cost_usd

    def record_usage(
        self,
        tokens: int = 0,
        cost_usd: float = 0.0,
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        """Record token/cost usage and return any triggered alerts."""
        self.used_tokens += tokens
        self.used_cost_usd += cost_usd

        # Track per-provider costs
        if provider:
            if provider not in self.provider_costs:
                self.provider_costs[provider] = {"cost_usd": 0.0, "tokens": 0}
            self.provider_costs[provider]["cost_usd"] += cost_usd
            self.provider_costs[provider]["tokens"] += tokens
            if model:
                model_key = f"model:{model}"
                if model_key not in self.provider_costs[provider]:
                    self.provider_costs[provider][model_key] = {"cost_usd": 0.0, "tokens": 0}
                self.provider_costs[provider][model_key]["cost_usd"] += cost_usd
                self.provider_costs[provider][model_key]["tokens"] += tokens

        # Check for alerts
        alerts: list[dict[str, Any]] = []
        for threshold in self.alert_thresholds:
            if threshold not in self.triggered_alerts:
                token_util = self.token_utilization
                cost_util = self.cost_utilization
                max_util = max(token_util, cost_util)
                if max_util >= threshold:
                    self.triggered_alerts.add(threshold)
                    alerts.append({
                        "threshold": threshold,
                        "threshold_pct": int(threshold * 100),
                        "token_utilization": token_util,
                        "cost_utilization": cost_util,
                        "remaining_tokens": self.remaining_tokens,
                        "remaining_cost_usd": self.remaining_cost,
                    })
        return {"alerts": alerts, "exceeded": self.is_exceeded()}

    def is_exceeded(self) -> bool:
        """Check if budget has been exceeded."""
        if self.max_tokens > 0 and self.used_tokens >= self.max_tokens:
            return True
        if self.max_cost_usd > 0 and self.used_cost_usd >= self.max_cost_usd:
            return True
        return False

    def get_status(self) -> dict[str, Any]:
        """Return current budget status."""
        return {
            "max_tokens": self.max_tokens,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens,
            "token_utilization": self.token_utilization,
            "max_cost_usd": self.max_cost_usd,
            "used_cost_usd": self.used_cost_usd,
            "remaining_cost_usd": self.remaining_cost,
            "cost_utilization": self.cost_utilization,
            "provider_costs": dict(self.provider_costs),
            "alerts_triggered": [t for t in self.triggered_alerts],
            "exceeded": self.is_exceeded(),
        }

    @classmethod
    def from_env(cls) -> "ContextBudget | None":
        """Create budget from environment variables."""
        max_tokens = int(os.getenv("GESTALT_CONTEXT_BUDGET_TOKENS", "0") or "0")
        max_cost = float(os.getenv("GESTALT_CONTEXT_BUDGET_COST", "0") or "0")

        if max_tokens <= 0 and max_cost <= 0:
            return None

        return cls(
            max_tokens=max_tokens,
            max_cost_usd=max_cost,
        )


@dataclass(slots=True)
class GestaltRuntime:
    router: Router
    persona_engine: PersonaEngine
    provider_router: ProviderRouter
    tool_runner: ToolRunner
    memory_manager: MemoryManager
    summary_engine: DeterministicSummary
    rag_store: RAGStore
    personas: PersonaCatalog
    tool_policy: ToolPolicy
    session_states: dict[str, RuntimeSessionState] = field(default_factory=dict)
    context_cache: dict[str, ContextCacheEntry] = field(default_factory=dict)
    context_cache_ttl_seconds: int = 1200
    context_cache_max_entries: int = 200
    context_cache_max_per_session: int = 3
    scheduler: Any = None
    _goal_scheduling_enabled: bool = False
    trace_emitter: TraceEmitter = field(default_factory=TraceEmitter)
    memory_coordinator: MemoryCoordinator | None = None

    async def handle_event(self, event: Event) -> Response:
        envelope = await self.handle_event_envelope(event)
        text = ""
        persona_id = str(event.metadata.get("persona_id") or "default")
        metadata: dict[str, Any] = {
            "event_id": envelope.event_id,
            "session_id": envelope.session_id,
        }

        for output in envelope.outputs:
            if isinstance(output, TextOutput) and not text:
                text = output.text
                if output.persona_id:
                    persona_id = output.persona_id
            elif isinstance(output, ErrorOutput) and not text:
                text = output.message

        metadata["mutations"] = [
            {"path": m.path, "old": m.old, "new": m.new} for m in envelope.mutations
        ]
        metadata["outputs"] = [self._output_to_dict(item) for item in envelope.outputs]
        return Response(text=text, persona_id=persona_id, metadata=metadata)

    async def tick(self) -> dict[str, Any]:
        """Execute a scheduler tick for goal-based scheduling.

        Returns dict with scheduler_present, scheduler_enabled, work_done, error.
        """
        result: dict[str, Any] = {
            "scheduler_present": False,
            "scheduler_enabled": False,
            "work_done": False,
            "error": None,
        }

        # Check if scheduler is present
        if self.scheduler is None:
            return result

        result["scheduler_present"] = True

        # Check if goal scheduling is enabled via env var (cached)
        if not self._goal_scheduling_enabled:
            env_value = os.getenv("ENABLE_GOAL_SCHEDULING", "").lower()
            self._goal_scheduling_enabled = env_value in ("1", "true", "yes", "on")

        result["scheduler_enabled"] = self._goal_scheduling_enabled

        # Only call scheduler if enabled
        if not self._goal_scheduling_enabled:
            return result

        try:
            work_done = await self.scheduler.tick()
            result["work_done"] = bool(work_done)
        except Exception as e:
            result["work_done"] = False
            result["error"] = str(e)

        return result

    def __post_init__(self) -> None:
        ttl_raw = int(
            os.getenv("GESTALT_CONTEXT_CACHE_TTL_SECONDS", "1200") or "1200"
        )
        max_entries_raw = int(
            os.getenv("GESTALT_CONTEXT_CACHE_MAX_ENTRIES", "200") or "200"
        )
        max_per_session_raw = int(
            os.getenv("GESTALT_CONTEXT_CACHE_MAX_PER_SESSION", "3") or "3"
        )
        self.context_cache_ttl_seconds = max(30, ttl_raw)
        self.context_cache_max_entries = max(20, max_entries_raw)
        self.context_cache_max_per_session = max(1, max_per_session_raw)
        # Initialize memory_coordinator if not provided (backward compatibility)
        if self.memory_coordinator is None:
            self.memory_coordinator = MemoryCoordinator(manager=self.memory_manager)

    # ------------------------------------------------------------------
    # Memory Coordinator methods (Phase 3 Slice 3: Memory Scoping)
    # ------------------------------------------------------------------

    async def get_typed_memory_context(
        self,
        session_id: str,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> TypedMemoryContext:
        """Get typed memory context for a session.

        This method provides access to strongly-typed memory context through
        the memory coordinator. It returns recent turns, facts, preferences,
        procedures, and action history as typed objects.

        Args:
            session_id: Session identifier for tracking
            namespace: Memory namespace (persona_id + room_id)
            limit: Maximum number of recent turns to load

        Returns:
            TypedMemoryContext with all typed memory elements
        """
        del session_id  # Reserved for future session-scoped context
        if self.memory_coordinator is None:
            raise RuntimeError("Memory coordinator not initialized")
        return await self.memory_coordinator.get_typed_context(
            namespace=namespace, limit=limit
        )

    async def record_turn(
        self,
        session_id: str,
        namespace: MemoryNamespace,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> "ShortTermTurn":
        """Record a conversation turn via the coordinator.

        Args:
            session_id: Session identifier for grouping
            namespace: Memory namespace
            role: Speaker role ("user", "assistant", or "system")
            content: The message content
            metadata: Additional turn metadata

        Returns:
            The created ShortTermTurn
        """
        if self.memory_coordinator is None:
            raise RuntimeError("Memory coordinator not initialized")
        return await self.memory_coordinator.record_turn(
            namespace=namespace,
            role=role,
            content=content,
            session_id=session_id,
            metadata=metadata,
        )

    async def store_memory_fact(
        self,
        session_id: str,
        namespace: MemoryNamespace,
        content: str,
        source: str = "runtime",
        confidence: float = 1.0,
    ) -> "Fact":
        """Store a fact via the coordinator.

        Args:
            session_id: Session identifier for tracking
            namespace: Memory namespace
            content: The fact content
            source: Origin of the fact
            confidence: Reliability score (0.0-1.0)

        Returns:
            The created Fact
        """
        del session_id  # Reserved for future session-scoped tracking
        if self.memory_coordinator is None:
            raise RuntimeError("Memory coordinator not initialized")
        from memory.types import MemoryScope

        return await self.memory_coordinator.store_fact(
            namespace=namespace,
            content=content,
            source=source,
            confidence=confidence,
            scope=MemoryScope.PERSONA,
        )

    async def get_memory_facts(
        self,
        session_id: str,
        namespace: MemoryNamespace,
        limit: int = 50,
    ) -> list["Fact"]:
        """Get facts via the coordinator.

        Args:
            session_id: Session identifier for tracking
            namespace: Memory namespace
            limit: Maximum number of facts to return

        Returns:
            List of Facts
        """
        del session_id  # Reserved for future session-scoped filtering
        if self.memory_coordinator is None:
            raise RuntimeError("Memory coordinator not initialized")
        from memory.types import MemoryScope

        return await self.memory_coordinator.get_facts(
            namespace=namespace,
            scope=MemoryScope.PERSONA,
            limit=limit,
        )

    async def to_memory_context_bundle(
        self,
        typed_context: TypedMemoryContext,
    ) -> MemoryContextBundle:
        """Convert TypedMemoryContext to legacy MemoryContextBundle.

        This helper enables backward compatibility with existing code that
        expects the legacy bundle format.

        Args:
            typed_context: The typed memory context to convert

        Returns:
            MemoryContextBundle for backward compatibility
        """
        if self.memory_coordinator is None:
            raise RuntimeError("Memory coordinator not initialized")
        return self.memory_coordinator.to_memory_context_bundle(typed_context)

    @staticmethod
    def _safe_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return ToolRunner._safe_trace_args(name=tool_name, arguments=arguments)

    async def _record_tool_action(
        self,
        *,
        session: RuntimeSessionState,
        room_id: str,
        action_type: str,
        tool_name: str | None,
        inputs: dict[str, Any],
        output: str,
        outcome: str,
        approval_state: str | None = None,
    ) -> ActionRecord:
        persona_id = session.persona_id or "default"
        if self.memory_coordinator is not None:
            record = await self.memory_coordinator.record_action(
                namespace=MemoryNamespace(
                    persona_id=persona_id,
                    room_id=room_id or "default",
                ),
                action_type=action_type,
                inputs=inputs,
                output=output,
                outcome=outcome,
                tool_name=tool_name,
                session_id=session.session_id,
                approval_state=approval_state,
            )
        else:
            record = ActionRecord(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                tool_name=tool_name,
                inputs=inputs,
                output=output,
                outcome=outcome,
                persona_id=persona_id,
                session_id=session.session_id,
                timestamp=datetime.now(timezone.utc),
                approval_state=approval_state,
            )
        session.recent_action_records.append(record)
        session.recent_action_records = session.recent_action_records[-20:]
        return record

    async def _partition_tool_calls_for_approval(
        self,
        *,
        event: Event,
        session: RuntimeSessionState,
        tool_calls: list[ToolCall],
        parent_span_id: str | None = None,
    ) -> tuple[list[ToolCall], list[ToolResult], list[dict[str, Any]], list[StructuredOutput]]:
        executable_calls: list[ToolCall] = []
        gated_results: list[ToolResult] = []
        gated_traces: list[dict[str, Any]] = []
        approval_outputs: list[StructuredOutput] = []

        for call in tool_calls:
            if not self.tool_policy.requires_approval(
                call.name,
                yolo_enabled=session.yolo_enabled,
            ):
                executable_calls.append(call)
                continue

            approval_id = str(uuid.uuid4())
            risk_tier = self.tool_policy.risk_tier_for_tool(call.name)
            safe_args = self._safe_tool_arguments(call.name, call.arguments)
            approval_payload = {
                "approval_id": approval_id,
                "tool_name": call.name,
                "risk_tier": risk_tier.value,
                "arguments": safe_args,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "environment": event.platform,
                "persona_id": session.persona_id,
            }
            session.pending_tool_approvals[approval_id] = dict(approval_payload)
            self.trace_emitter.emit_approval_request(
                session_id=session.session_id,
                span_id=str(uuid.uuid4()),
                request_type="tool_call",
                request_id=approval_id,
                data=approval_payload,
                parent_span_id=parent_span_id,
            )
            gated_traces.append(
                {
                    "trace_type": "approval_request",
                    "request_id": approval_id,
                    "request_type": "tool_call",
                    "tool_name": call.name,
                    "risk_tier": risk_tier.value,
                    "arguments": safe_args,
                    "status": "pending",
                }
            )
            await self._record_tool_action(
                session=session,
                room_id=event.room_id,
                action_type="tool_approval",
                tool_name=call.name,
                inputs=safe_args,
                output="Pending operator approval",
                outcome="pending",
                approval_state="pending",
            )
            gated_results.append(
                ToolResult(
                    name=call.name,
                    error="Tool requires approval before execution",
                    metadata={
                        "approval_id": approval_id,
                        "approval_state": "pending",
                        "risk_tier": risk_tier.value,
                    },
                )
            )
            approval_outputs.append(
                StructuredOutput(kind="approval_request", data=approval_payload)
            )

        return executable_calls, gated_results, gated_traces, approval_outputs

    async def _record_tool_results(
        self,
        *,
        event: Event,
        session: RuntimeSessionState,
        results: list[ToolResult],
    ) -> None:
        for result in results:
            approval_state = str(result.metadata.get("approval_state") or "") or None
            output_summary = str(result.error) if result.error else str(result.output)[:2000]
            await self._record_tool_action(
                session=session,
                room_id=event.room_id,
                action_type="tool_call",
                tool_name=result.name,
                inputs={},
                output=output_summary,
                outcome="error" if result.error else "success",
                approval_state=approval_state,
            )

    async def close(self) -> None:
        """Release runtime-owned transient state for adapter shutdown."""
        self.session_states.clear()
        self.context_cache.clear()
        # Clear trace emitter state
        if hasattr(self, "trace_emitter") and self.trace_emitter:
            self.trace_emitter.clear_all()
        # Close provider router to release aiohttp sessions
        if hasattr(self, "provider_router") and self.provider_router:
            close_fn = getattr(self.provider_router, "close", None)
            if callable(close_fn):
                result = close_fn()
                if inspect.isawaitable(result):
                    await result

    async def handle_event_envelope(self, event: Event) -> ResponseEnvelope:
        session_id = (
            event.session_id or f"{event.platform}:{event.room_id or 'default'}"
        )
        event.session_id = session_id
        session = self._get_or_create_session(event)
        mutations = self._apply_event_metadata(session=session, event=event)

        # Emit adapter ingress trace
        ingress_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_adapter_ingress(
            session_id=session_id,
            span_id=ingress_span_id,
            data={
                "event_type": event.type,
                "platform": event.platform,
                "text_preview": event.text[:200] if event.text else "",
                "kind": event.kind,
                "user_id": event.user_id,
                "room_id": event.room_id,
            },
        )

        is_command = event.kind == EventKind.COMMAND.value or event.type == "command"
        if event.text.strip().startswith("/"):
            is_command = True

        if is_command:
            result_outputs, result_mutations = await self._handle_command_event(
                event=event,
                session=session,
            )
            self._append_session_traces(session, result_outputs)
            return ResponseEnvelope(
                event_id=event.event_id,
                session_id=session_id,
                outputs=result_outputs,
                mutations=mutations + result_mutations,
            )

        response, traces = await self._run_chat_flow(event=event, session=session)
        session.last_tool_calls_used = len(response.tool_calls)

        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            TextOutput(text=response.text, persona_id=response.persona_id),
            StructuredOutput(kind="response_metadata", data=dict(response.metadata)),
        ]
        outputs.extend(traces)
        self._append_session_traces(session, outputs)
        return ResponseEnvelope(
            event_id=event.event_id,
            session_id=session_id,
            outputs=outputs,
            mutations=mutations,
        )

    async def stream_event(self, event: Event) -> AsyncIterator[dict[str, Any]]:
        session_id = event.session_id or f"{event.platform}:{event.room_id or 'default'}"
        event.session_id = session_id
        session = self._get_or_create_session(event)
        mutations = self._apply_event_metadata(session=session, event=event)

        is_command = event.kind == EventKind.COMMAND.value or event.type == "command"
        if event.text.strip().startswith("/"):
            is_command = True

        if is_command:
            envelope = await self.handle_event_envelope(event)
            for output in envelope.outputs:
                yield {"type": "output", "output": output, "event_id": envelope.event_id}
            for mutation in envelope.mutations:
                yield {"type": "mutation", "mutation": mutation, "event_id": envelope.event_id}
            return

        async for item in self._stream_chat_flow(event=event, session=session):
            payload_type = str(item.get("type") or "")
            if payload_type == "final":
                response = item["response"]
                traces = list(item["traces"])
                outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
                    TextOutput(text=response.text, persona_id=response.persona_id),
                    StructuredOutput(kind="response_metadata", data=dict(response.metadata)),
                    *traces,
                ]
                self._append_session_traces(session, outputs)
                for output in outputs:
                    yield {"type": "output", "output": output, "event_id": event.event_id}
                for mutation in mutations:
                    yield {"type": "mutation", "mutation": mutation, "event_id": event.event_id}
                continue
            yield item

    async def _run_chat_flow(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> tuple[Response, list[TraceOutput]]:
        persona = self.router.select_persona(event, self.personas)
        if not session.persona_id:
            session.persona_id = persona.persona_id
        namespace = MemoryNamespace(
            persona_id=persona.persona_id, room_id=event.room_id or "default"
        )
        memory_context = await self.memory_manager.load_context(namespace=namespace, limit=12)
        
        # Emit memory assembly trace
        root_span_id = str(uuid.uuid4())
        mem_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_memory_assembly(
            session_id=session.session_id,
            span_id=mem_span_id,
            memory_type="context_build",
            data={
                "persona_id": persona.persona_id,
                "message_count": len(memory_context.recent_history),
                "summary_length": len(memory_context.summary),
                "fact_count": len(memory_context.facts),
            },
            parent_span_id=root_span_id,
        )
        
        rag_results = await self.rag_store.search(
            persona_id=persona.persona_id,
            room_id=namespace.room_id,
            query=event.text,
        )
        rag_context = "\n".join([r.content for r in rag_results])
        mode_name = session.mode or self._default_mode_for_persona(persona)
        provider_name = (
            session.provider_override
            or self.provider_router.resolve_provider_name(persona.persona_id, session.mode)
        )
        provider = self.provider_router.providers.get(provider_name)
        if provider is None:
            provider_name = self.provider_router.default_provider_name
            provider = self.provider_router.providers[provider_name]
        model_override = session.model_override.strip() or None
        model = model_override or self._provider_model(provider)
        allowed_tools = self.tool_policy.allowed_tools(
            persona_id=persona.persona_id,
            environment=event.platform,
        )
        all_schemas = self.tool_runner.registry.schemas(allowlist=allowed_tools)
        tool_schemas = [
            schema
            for schema in all_schemas
            if self.tool_policy.is_tool_allowed(
                str(schema.get("name") or ""), allowed_tools
            )
        ]
        provider_messages, cache_trace, request_hints = (
            await self._build_provider_messages_with_cache(
                session=session,
                persona=persona,
                memory_context=memory_context,
                rag_context=rag_context,
                mode_name=mode_name,
                provider_name=provider_name,
                model_name=model,
                tool_schemas=tool_schemas,
            )
        )

        if event.type == "tick":
            provider_messages.append(
                ProviderMessage(
                    role="user",
                    content="Decide if you should act right now. If not, answer with 'pass'.",
                )
            )
        else:
            provider_messages.append(ProviderMessage(role="user", content=event.text))

        # root_span_id already set above
        decision_trace = self._build_span_trace(
            trace_type="decision",
            session_id=session.session_id,
            parent_span_id=root_span_id,
            data={
                "reason": "policy-filtered tool schemas ready",
                "allowed_count": len(tool_schemas),
                "max_tool_calls_per_turn": self.tool_policy.max_tool_calls_per_turn,
                "network_enabled": self.tool_policy.network_enabled,
                "dangerous_enabled": self.tool_policy.dangerous_enabled,
            },
        )
        
        # Emit provider request trace via emitter
        req_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_provider_request(
            session_id=session.session_id,
            span_id=req_span_id,
            provider=provider_name,
            model=model,
            data={
                "tool_count": len(tool_schemas),
                "message_count": len(provider_messages),
            },
            parent_span_id=root_span_id,
        )

        # Initialize budget tracking
        budget_traces: list[TraceOutput] = []

        # Check context budget before LLM call
        budget_exceeded = False
        if session.context_budget is not None:
            if session.context_budget.is_exceeded():
                budget_exceeded = True
                budget_traces.append(
                    self._build_span_trace(
                        trace_type="budget_exceeded",
                        session_id=session.session_id,
                        parent_span_id=root_span_id,
                        data=session.context_budget.get_status(),
                    )
                )
            else:
                # Record pre-call budget status
                budget_status = session.context_budget.get_status()
                budget_traces.append(
                    self._build_span_trace(
                        trace_type="budget_check",
                        session_id=session.session_id,
                        parent_span_id=root_span_id,
                        data={
                            "utilization": budget_status["token_utilization"],
                            "cost_utilization": budget_status["cost_utilization"],
                            "remaining_tokens": budget_status["remaining_tokens"],
                            "remaining_cost": budget_status["remaining_cost_usd"],
                        },
                    )
                )

        # If budget exceeded, return early with error
        if budget_exceeded:
            # Emit error trace
            err_span_id = str(uuid.uuid4())
            self.trace_emitter.emit_error(
                session_id=session.session_id,
                span_id=err_span_id,
                error_code="BUDGET_EXCEEDED",
                message="Context budget exceeded",
                data=session.context_budget.get_status() if session.context_budget else {},
                parent_span_id=root_span_id,
            )
            error_response = Response(
                text="Context budget exceeded. Please check usage with /status.",
                persona_id=session.persona_id or "system",
                metadata={"error": "budget_exceeded", "budget": session.context_budget.get_status() if session.context_budget else {}},
            )
            return error_response, [decision_trace] + budget_traces

        provider_started = perf_counter()
        provider_response = await provider.chat(
            messages=provider_messages,
            tools=tool_schemas,
            model_override=model_override,
            request_hints=request_hints,
        )
        provider_duration = int((perf_counter() - provider_started) * 1000)
        combined_usage = self._normalize_provider_usage(
            response=provider_response,
            request_messages=provider_messages,
            response_text=provider_response.content or "",
        )
        self._record_session_provider_usage(session=session, usage=combined_usage)

        # Record usage in budget
        if session.context_budget is not None:
            result = session.context_budget.record_usage(
                tokens=combined_usage.input_tokens + combined_usage.output_tokens,
                cost_usd=0.0,  # Will be estimated by budget
                provider=provider_name,
                model=model,
            )
            # Emit budget traces including alerts
            if result["alerts"]:
                for alert in result["alerts"]:
                    budget_traces.append(
                        self._build_span_trace(
                            trace_type="budget_alert",
                            session_id=session.session_id,
                            parent_span_id=root_span_id,
                            data=alert,
                        )
                    )

        provider_trace = self._build_span_trace(
            trace_type="provider",
            session_id=session.session_id,
            parent_span_id=root_span_id,
            data={
                "provider": provider_name,
                "model": model,
                "duration_ms": provider_duration,
                "tool_call_count": len(provider_response.tool_calls),
                "input_tokens": combined_usage.input_tokens,
                "output_tokens": combined_usage.output_tokens,
                "cached_input_tokens": combined_usage.cached_input_tokens,
                "budget_checked": session.context_budget is not None,
                "budget_status": session.context_budget.get_status() if session.context_budget else None,
            },
        )
        
        # Emit provider response trace via emitter
        resp_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_provider_response(
            session_id=session.session_id,
            span_id=resp_span_id,
            provider=provider_name,
            model=model,
            data={
                "duration_ms": provider_duration,
                "input_tokens": combined_usage.input_tokens,
                "output_tokens": combined_usage.output_tokens,
                "cached_input_tokens": combined_usage.cached_input_tokens,
                "tool_call_count": len(provider_response.tool_calls),
            },
            parent_span_id=root_span_id,
        )

        tool_calls = [
            ToolCall(name=t.name, arguments=t.arguments)
            for t in provider_response.tool_calls
        ]
        executed_results: list[ToolResult] = []
        tool_traces: list[TraceOutput] = []
        approval_outputs: list[StructuredOutput] = []

        if tool_calls:
            # Emit tool call traces
            for tc in tool_calls:
                tool_span_id = str(uuid.uuid4())
                self.trace_emitter.emit_tool_call(
                    session_id=session.session_id,
                    span_id=tool_span_id,
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    parent_span_id=root_span_id,
                )
            executable_calls, gated_results, gated_trace_dicts, approval_outputs = (
                await self._partition_tool_calls_for_approval(
                    event=event,
                    session=session,
                    tool_calls=tool_calls,
                    parent_span_id=root_span_id,
                )
            )
            executed_results.extend(gated_results)
            trace_dicts = list(gated_trace_dicts)
            if executable_calls:
                runner_results, runner_trace_dicts = await self.tool_runner.execute_with_trace(
                    persona_id=persona.persona_id,
                    environment=event.platform,
                    tool_calls=executable_calls,
                )
                executed_results.extend(runner_results)
                trace_dicts.extend(runner_trace_dicts)
                await self._record_tool_results(
                    event=event,
                    session=session,
                    results=runner_results,
                )
            tool_traces = [
                self._build_span_trace(
                    trace_type=str(item.get("trace_type") or "tool"),
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data=item,
                )
                for item in trace_dicts
            ]

        text = provider_response.content or ""
        if executed_results:
            tool_output_lines = []
            for result in executed_results:
                if result.error:
                    tool_output_lines.append(f"{result.name} error: {result.error}")
                else:
                    tool_output_lines.append(f"{result.name} output: {result.output}")
            provider_messages.append(
                ProviderMessage(
                    role="tool",
                    content="\n".join(tool_output_lines),
                )
            )
            follow_started = perf_counter()
            follow_up = await provider.chat(
                messages=provider_messages,
                tools=[],
                model_override=model_override,
                request_hints=request_hints,
            )
            follow_duration = int((perf_counter() - follow_started) * 1000)
            follow_usage = self._normalize_provider_usage(
                response=follow_up,
                request_messages=provider_messages,
                response_text=follow_up.content or "",
            )
            self._record_session_provider_usage(session=session, usage=follow_usage)
            combined_usage = self._merge_provider_usage(combined_usage, follow_usage)
            if session.context_budget is not None:
                session.context_budget.record_usage(
                    tokens=follow_usage.input_tokens + follow_usage.output_tokens,
                    cost_usd=0.0,
                    provider=provider_name,
                    model=model,
                )
            tool_traces.append(
                self._build_span_trace(
                    trace_type="provider",
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data={
                        "provider": provider_name,
                        "model": model,
                        "duration_ms": follow_duration,
                        "stage": "post_tool_follow_up",
                        "input_tokens": follow_usage.input_tokens,
                        "output_tokens": follow_usage.output_tokens,
                        "cached_input_tokens": follow_usage.cached_input_tokens,
                    },
                )
            )
            text = follow_up.content or text

        if not str(text).strip():
            text = (
                "I could not generate a response this turn. "
                "Run /status to verify provider/model settings."
            )

        state_mutation_trace: list[TraceOutput] = []
        if event.type != "tick":
            await self.memory_manager.write_buffer_message(
                namespace,
                {"role": "user", "content": event.text, "user_id": event.user_id},
            )
            await self.memory_manager.write_buffer_message(
                namespace,
                {
                    "role": "assistant",
                    "content": text,
                    "persona_id": persona.persona_id,
                },
            )
            await self.memory_manager.write_summary(
                namespace=namespace,
                recent_messages=[
                    {"role": "user", "content": event.text},
                    {"role": "assistant", "content": text},
                ],
            )
            await self.persona_engine.update_state(
                persona=persona,
                namespace=namespace,
                user_text=event.text,
                response_text=text,
            )
            await self.memory_manager.write_fact(
                namespace,
                f"Last user intent: {event.text[:120]}",
            )
            state_mutation_trace.append(
                self._build_span_trace(
                    trace_type="state",
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data={
                        "path": f"session:{session.session_id}",
                        "persona_id": persona.persona_id,
                        "mode": mode_name,
                    },
                )
            )

        response = Response(
            text=text,
            persona_id=persona.persona_id,
            tool_calls=tool_calls,
            metadata={
                "platform": event.platform,
                "room_id": event.room_id,
                "provider": provider_name,
                "model": model,
                "usage": {
                    "input_tokens": combined_usage.input_tokens,
                    "output_tokens": combined_usage.output_tokens,
                    "cached_input_tokens": combined_usage.cached_input_tokens,
                },
                "tool_results": [
                    {
                        "name": r.name,
                        "output": r.output,
                        "error": r.error,
                        "metadata": dict(r.metadata),
                    }
                    for r in executed_results
                ],
                "pending_approvals": [dict(output.data) for output in approval_outputs],
            },
        )
        traces = (
            [decision_trace, provider_trace]
            + tool_traces
            + state_mutation_trace
            + budget_traces
            + [cache_trace]
        )
        return response, traces

    async def _stream_chat_flow(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> AsyncIterator[dict[str, Any]]:
        persona = self.router.select_persona(event, self.personas)
        if not session.persona_id:
            session.persona_id = persona.persona_id
        namespace = MemoryNamespace(
            persona_id=persona.persona_id, room_id=event.room_id or "default"
        )
        memory_context = await self.memory_manager.load_context(namespace=namespace, limit=12)
        rag_results = await self.rag_store.search(
            persona_id=persona.persona_id,
            room_id=namespace.room_id,
            query=event.text,
        )
        rag_context = "\n".join([r.content for r in rag_results])
        mode_name = session.mode or self._default_mode_for_persona(persona)
        provider_name = (
            session.provider_override
            or self.provider_router.resolve_provider_name(persona.persona_id, session.mode)
        )
        provider = self.provider_router.providers.get(provider_name)
        if provider is None:
            provider_name = self.provider_router.default_provider_name
            provider = self.provider_router.providers[provider_name]
        model_override = session.model_override.strip() or None
        model = model_override or self._provider_model(provider)
        allowed_tools = self.tool_policy.allowed_tools(
            persona_id=persona.persona_id,
            environment=event.platform,
        )
        all_schemas = self.tool_runner.registry.schemas(allowlist=allowed_tools)
        tool_schemas = [
            schema
            for schema in all_schemas
            if self.tool_policy.is_tool_allowed(
                str(schema.get("name") or ""), allowed_tools
            )
        ]
        provider_messages, cache_trace, request_hints = (
            await self._build_provider_messages_with_cache(
                session=session,
                persona=persona,
                memory_context=memory_context,
                rag_context=rag_context,
                mode_name=mode_name,
                provider_name=provider_name,
                model_name=model,
                tool_schemas=tool_schemas,
            )
        )
        provider_messages.append(ProviderMessage(role="user", content=event.text))
        root_span_id = str(uuid.uuid4())
        decision_trace = self._build_span_trace(
            trace_type="decision",
            session_id=session.session_id,
            parent_span_id=root_span_id,
            data={
                "reason": "policy-filtered tool schemas ready",
                "allowed_count": len(tool_schemas),
                "max_tool_calls_per_turn": self.tool_policy.max_tool_calls_per_turn,
                "network_enabled": self.tool_policy.network_enabled,
                "dangerous_enabled": self.tool_policy.dangerous_enabled,
            },
        )
        yield {"type": "trace", "trace": decision_trace}
        stream_chat = getattr(provider, "stream_chat", None)
        if not callable(stream_chat):
            response, traces = await self._run_chat_flow(event=event, session=session)
            yield {"type": "final", "response": response, "traces": traces}
            return

        provider_started = perf_counter()
        content = ""
        provider_response = None
        async for chunk in stream_chat(
            messages=provider_messages,
            tools=tool_schemas,
            model_override=model_override,
            request_hints=request_hints,
        ):
            if chunk.kind == "text_delta" and chunk.text:
                content += chunk.text
                session.last_provider_at = datetime.now(timezone.utc)
                session.last_response_at = datetime.now(timezone.utc)
                session.last_persona_text = content
                yield {
                    "type": "text_delta",
                    "text": chunk.text,
                    "aggregate_text": content,
                    "persona_id": persona.persona_id,
                }
                continue
            if chunk.kind == "response" and chunk.response is not None:
                provider_response = chunk.response

        if provider_response is None:
            response, traces = await self._run_chat_flow(event=event, session=session)
            yield {"type": "final", "response": response, "traces": traces}
            return

        provider_duration = int((perf_counter() - provider_started) * 1000)
        combined_usage = self._normalize_provider_usage(
            response=provider_response,
            request_messages=provider_messages,
            response_text=provider_response.content or content,
        )
        self._record_session_provider_usage(session=session, usage=combined_usage)
        provider_trace = self._build_span_trace(
            trace_type="provider",
            session_id=session.session_id,
            parent_span_id=root_span_id,
            data={
                "provider": provider_name,
                "model": model,
                "duration_ms": provider_duration,
                "tool_call_count": len(provider_response.tool_calls),
                "input_tokens": combined_usage.input_tokens,
                "output_tokens": combined_usage.output_tokens,
                "cached_input_tokens": combined_usage.cached_input_tokens,
                "streamed": True,
            },
        )

        tool_calls = [ToolCall(name=t.name, arguments=t.arguments) for t in provider_response.tool_calls]
        executed_results: list[ToolResult] = []
        tool_traces: list[TraceOutput] = []
        approval_outputs: list[StructuredOutput] = []
        text = provider_response.content or content
        if tool_calls:
            executable_calls, gated_results, gated_trace_dicts, approval_outputs = (
                await self._partition_tool_calls_for_approval(
                    event=event,
                    session=session,
                    tool_calls=tool_calls,
                    parent_span_id=root_span_id,
                )
            )
            executed_results.extend(gated_results)
            trace_dicts = list(gated_trace_dicts)
            if executable_calls:
                runner_results, runner_trace_dicts = await self.tool_runner.execute_with_trace(
                    persona_id=persona.persona_id,
                    environment=event.platform,
                    tool_calls=executable_calls,
                )
                executed_results.extend(runner_results)
                trace_dicts.extend(runner_trace_dicts)
                await self._record_tool_results(
                    event=event,
                    session=session,
                    results=runner_results,
                )
            tool_traces = [
                self._build_span_trace(
                    trace_type=str(item.get("trace_type") or "tool"),
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data=item,
                )
                for item in trace_dicts
            ]
            
            # Emit tool result traces via emitter
            for result in executed_results:
                result_span_id = str(uuid.uuid4())
                self.trace_emitter.emit_tool_result(
                    session_id=session.session_id,
                    span_id=result_span_id,
                    tool_name=result.name,
                    output=str(result.output)[:200] if result.output else "",
                    error=result.error,
                    parent_span_id=root_span_id,
                )
            tool_output_lines = []
            for result in executed_results:
                if result.error:
                    tool_output_lines.append(f"{result.name} error: {result.error}")
                else:
                    tool_output_lines.append(f"{result.name} output: {result.output}")
            provider_messages.append(
                ProviderMessage(role="tool", content="\n".join(tool_output_lines))
            )
            follow_started = perf_counter()
            follow_up = await provider.chat(
                messages=provider_messages,
                tools=[],
                model_override=model_override,
                request_hints=request_hints,
            )
            follow_duration = int((perf_counter() - follow_started) * 1000)
            follow_usage = self._normalize_provider_usage(
                response=follow_up,
                request_messages=provider_messages,
                response_text=follow_up.content or "",
            )
            self._record_session_provider_usage(session=session, usage=follow_usage)
            combined_usage = self._merge_provider_usage(combined_usage, follow_usage)
            tool_traces.append(
                self._build_span_trace(
                    trace_type="provider",
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data={
                        "provider": provider_name,
                        "model": model,
                        "duration_ms": follow_duration,
                        "stage": "post_tool_follow_up",
                        "input_tokens": follow_usage.input_tokens,
                        "output_tokens": follow_usage.output_tokens,
                        "cached_input_tokens": follow_usage.cached_input_tokens,
                    },
                )
            )
            text = follow_up.content or text

        if not str(text).strip():
            text = (
                "I could not generate a response this turn. "
                "Run /status to verify provider/model settings."
            )

        state_mutation_trace: list[TraceOutput] = []
        if event.type != "tick":
            await self.memory_manager.write_buffer_message(
                namespace,
                {"role": "user", "content": event.text, "user_id": event.user_id},
            )
            await self.memory_manager.write_buffer_message(
                namespace,
                {"role": "assistant", "content": text, "persona_id": persona.persona_id},
            )
            await self.memory_manager.write_summary(
                namespace=namespace,
                recent_messages=[
                    {"role": "user", "content": event.text},
                    {"role": "assistant", "content": text},
                ],
            )
            await self.persona_engine.update_state(
                persona=persona,
                namespace=namespace,
                user_text=event.text,
                response_text=text,
            )
            await self.memory_manager.write_fact(
                namespace,
                f"Last user intent: {event.text[:120]}",
            )
            state_mutation_trace.append(
                self._build_span_trace(
                    trace_type="state",
                    session_id=session.session_id,
                    parent_span_id=root_span_id,
                    data={
                        "path": f"session:{session.session_id}",
                        "persona_id": persona.persona_id,
                        "mode": mode_name,
                    },
                )
            )

        response = Response(
            text=text,
            persona_id=persona.persona_id,
            tool_calls=tool_calls,
            metadata={
                "platform": event.platform,
                "room_id": event.room_id,
                "provider": provider_name,
                "model": model,
                "streamed": True,
                "usage": {
                    "input_tokens": combined_usage.input_tokens,
                    "output_tokens": combined_usage.output_tokens,
                    "cached_input_tokens": combined_usage.cached_input_tokens,
                },
                "tool_results": [
                    {
                        "name": r.name,
                        "output": r.output,
                        "error": r.error,
                        "metadata": dict(r.metadata),
                    }
                    for r in executed_results
                ],
                "pending_approvals": [dict(output.data) for output in approval_outputs],
            },
        )
        traces = [provider_trace] + tool_traces + state_mutation_trace + [cache_trace]
        yield {"type": "final", "response": response, "traces": traces}

    async def _handle_command_event(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> tuple[
        list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
        list[StateMutation],
    ]:
        registry = self._build_command_registry()
        parsed = registry.parse(event.text)
        
        # Emit command dispatch trace
        command_name = ""
        if not isinstance(parsed, ErrorOutput):
            command_name = parsed.name if hasattr(parsed, 'name') else ""
        cmd_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_command_dispatch(
            session_id=session.session_id,
            span_id=cmd_span_id,
            command=command_name or "unknown",
            args=parsed.args if hasattr(parsed, 'args') else {},
        )
        if isinstance(parsed, ErrorOutput):
            return [parsed], []

        validated = registry.validate(parsed)
        if isinstance(validated, ErrorOutput):
            return [validated], []

        if validated.name == "help":
            return self._command_help(registry), []

        if validated.name == "status":
            return self._command_status(event=event, session=session), []

        if validated.name == "context":
            action = str(validated.args.get("action") or "").strip().lower()
            return self._command_context(
                event=event,
                session=session,
                action=action,
            ), []

        if validated.name == "tools":
            return self._command_tools(event=event, session=session), []

        if validated.name == "trace":
            limit = int(validated.args.get("limit") or 10)
            return self._command_trace(session=session, limit=limit), []

        if validated.name == "recap":
            return await self._command_recap(event=event, session=session), []

        if validated.name == "continue":
            outputs = await self._command_continue(event=event, session=session)
            return outputs, []

        if validated.name == "stop":
            return self._command_stop(session=session), []

        if validated.name == "eval":
            outputs = await self._command_eval(session=session)
            return outputs, []

        if validated.name == "mode":
            mode_name = str(validated.args.get("name") or "").strip()
            return self._command_mode(mode_name=mode_name, event=event, session=session)

        if validated.name == "yolo":
            state = str(validated.args.get("state") or "").strip().lower()
            confirm = bool(validated.args.get("confirm") or False)
            return self._command_yolo(session=session, state=state, confirm=confirm), []

        if validated.name in {"persona", "switch"}:
            name = str(validated.args.get("name") or "").strip().lower()
            return self._command_persona(session=session, name=name), []

        if validated.name == "model":
            spec = str(validated.args.get("spec") or "").strip()
            return self._command_model(session=session, spec=spec), []

        if validated.name == "models":
            provider = str(validated.args.get("provider") or "").strip().lower()
            return self._command_models(session=session, provider_name=provider), []

        if validated.name == "shell":
            command = str(validated.args.get("command") or "")
            outputs = await self._command_shell(
                event=event,
                session=session,
                command=command,
            )
            return outputs, []

        if validated.name == "diff":
            path = str(validated.args.get("path") or "")
            content = str(validated.args.get("content") or "")
            outputs, mutations = self._command_diff_preview(
                session=session,
                path=path,
                new_content=content,
            )
            return outputs, mutations

        if validated.name == "apply":
            confirmation_id = str(validated.args.get("id") or "")
            outputs, mutations = self._command_apply_diff(
                session=session,
                confirmation_id=confirmation_id,
            )
            return outputs, mutations

        if validated.name == "reject":
            confirmation_id = str(validated.args.get("id") or "")
            outputs, mutations = self._command_reject_diff(
                session=session,
                confirmation_id=confirmation_id,
            )
            return outputs, mutations

        if validated.name == "autopilot":
            outputs = await self._command_autopilot(
                event=event,
                session=session,
                steps=int(validated.args.get("steps") or 3),
                confirm=bool(validated.args.get("confirm") or False),
            )
            return outputs, []

        return [
            ErrorOutput(
                code="UNKNOWN_COMMAND",
                message=f"Unknown command '/{validated.name}'.",
                hint="Run /help for available commands.",
            )
        ], []

    def _build_command_registry(self) -> CommandRegistry:
        registry = CommandRegistry()
        registry.register(
            spec=self._command_spec(
                name="help",
                description="List available commands.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/help"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="status",
                description="Show effective runtime state.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/status"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="context",
                description="Inspect or reset runtime context cache for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {"action": {"type": "string", "enum": ["reset"]}},
                },
                examples=["/context", "/context reset"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="tools",
                description="List available tools with risk tier and policy state.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/tools"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="trace",
                description="Show recent trace spans for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "minimum": 1}},
                },
                examples=["/trace", "/trace --limit 20"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="recap",
                description="Summarize current session conversation history.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/recap"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="continue",
                description="Continue autopilot from next checkpoint.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/continue"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="stop",
                description="Stop and clear active autopilot plan.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/stop"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="eval",
                description="Run scenario evaluation suite and return summary.",
                arguments_schema={"type": "object", "properties": {}},
                examples=["/eval"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="mode",
                description="Switch persona mode for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
                examples=["/mode tai_core", "/mode tai_anis"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="yolo",
                description="Show or toggle yolo mode for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "state": {"type": "string", "enum": ["on", "off"]},
                        "confirm": {"type": "boolean"},
                    },
                },
                examples=["/yolo", "/yolo on", "/yolo on --confirm", "/yolo off"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="persona",
                description="Show or switch active persona for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
                examples=["/persona", "/persona tai"],
                aliases=["/switch"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="model",
                description="Show or set provider/model override for this session.",
                arguments_schema={
                    "type": "object",
                    "properties": {"spec": {"type": "string"}},
                },
                examples=["/model", "/model openai/gpt-4o-mini", "/model reset"],
                aliases=["/m"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="models",
                description="List providers and known model options.",
                arguments_schema={
                    "type": "object",
                    "properties": {"provider": {"type": "string"}},
                },
                examples=["/models", "/models openai"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="shell",
                description="Execute a shell command through runtime tool policy.",
                arguments_schema={
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
                examples=["/shell --command 'ls -la'"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="diff",
                description="Preview unified diff and queue a pending file write.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
                examples=[
                    "/diff --path notes.txt --content 'new text'",
                    "/diff notes.txt 'new text'",
                ],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="apply",
                description="Apply a queued diff confirmation by id.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                    },
                    "required": ["id"],
                },
                examples=["/apply --id abc123", "/apply abc123"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="reject",
                description="Reject and clear a queued diff confirmation by id.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                    },
                    "required": ["id"],
                },
                examples=["/reject --id abc123", "/reject abc123"],
            ),
        )
        registry.register(
            spec=self._command_spec(
                name="autopilot",
                description="Run checkpointed safe autopilot plan.",
                arguments_schema={
                    "type": "object",
                    "properties": {
                        "steps": {"type": "integer", "minimum": 3, "maximum": 7},
                        "confirm": {"type": "boolean"},
                    },
                },
                examples=["/autopilot --steps 3", "/autopilot --steps 3 --confirm"],
            ),
        )
        return registry

    @staticmethod
    def _command_spec(
        name: str,
        description: str,
        arguments_schema: dict[str, Any],
        examples: list[str],
        aliases: list[str] | None = None,
    ):
        from core.commands import CommandSpec

        return CommandSpec(
            name=name,
            description=description,
            arguments_schema=arguments_schema,
            examples=examples,
            aliases=aliases,
        )

    def _command_help(
        self, registry: CommandRegistry
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        command_items = self.list_commands(registry=registry)
        lines = ["Available commands:"]
        for item in command_items:
            aliases = item.get("aliases") or []
            alias_suffix = (
                f" (aliases: {', '.join(str(alias) for alias in aliases)})"
                if aliases
                else ""
            )
            lines.append(f"- {item['usage']}: {item['description']}{alias_suffix}")
        return [
            TextOutput(text="\n".join(lines), persona_id="system"),
            StructuredOutput(kind="command_help", data={"commands": command_items}),
        ]

    def list_commands(
        self,
        registry: CommandRegistry | None = None,
    ) -> list[dict[str, Any]]:
        command_registry = registry or self._build_command_registry()
        command_items: list[dict[str, Any]] = []
        for spec in command_registry.specs():
            args = self._command_argument_hint(spec.arguments_schema)
            usage = f"/{spec.name}"
            if args:
                usage = f"{usage} {args}"
            command_items.append(
                {
                    "name": spec.name,
                    "args": args,
                    "usage": usage,
                    "description": spec.description,
                    "aliases": list(spec.aliases or []),
                    "arguments_schema": spec.arguments_schema,
                    "examples": list(spec.examples),
                }
            )
        return command_items

    def get_status_snapshot(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = Event(
            type="command",
            kind=EventKind.COMMAND.value,
            text="/status",
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            metadata={
                "persona_id": persona_id,
                "mode": mode,
                "flags": dict(flags or {}),
            },
        )
        session = self._get_or_create_session(event)
        outputs = self._command_status(event=event, session=session)
        for output in outputs:
            if isinstance(output, StructuredOutput) and output.kind == "command_status":
                return dict(output.data)
        return {}

    def get_tools_snapshot(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        event = Event(
            type="command",
            kind=EventKind.COMMAND.value,
            text="/tools",
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            metadata={
                "persona_id": persona_id,
                "mode": mode,
                "flags": dict(flags or {}),
            },
        )
        session = self._get_or_create_session(event)
        outputs = self._command_tools(event=event, session=session)
        for output in outputs:
            if isinstance(output, StructuredOutput) and output.kind == "command_tools":
                tools = output.data.get("tools")
                if isinstance(tools, list):
                    return [dict(item) for item in tools if isinstance(item, dict)]
        return []

    def get_session_snapshot(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = Event(
            type="command",
            kind=EventKind.COMMAND.value,
            text="/status",
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            metadata={
                "persona_id": persona_id,
                "mode": mode,
                "flags": dict(flags or {}),
            },
        )
        session = self._get_or_create_session(event)
        provider_name = session.provider_override or self.provider_router.resolve_provider_name(
            session.persona_id or persona_id or self.router.default_persona_id,
            session.mode or mode or "default",
        )
        provider = self.provider_router.providers.get(provider_name)
        return {
            "session_id": session.session_id,
            "persona_id": session.persona_id or persona_id or self.router.default_persona_id,
            "mode": session.mode or mode or "default",
            "platform": platform,
            "room_id": room_id,
            "flags": dict(session.flags),
            "yolo": bool(session.yolo_enabled),
            "provider": provider_name,
            "model": session.model_override or self._provider_model(provider),
            "social": self.get_social_state_snapshot(
                session_id=session.session_id,
                persona_id=session.persona_id or persona_id,
                mode=session.mode or mode,
                platform=platform,
                room_id=room_id,
                flags=session.flags,
            ),
            "last_response_at": session.last_response_at.isoformat()
            if session.last_response_at
            else None,
            "last_persona_text": session.last_persona_text,
            "autopilot_active": bool(session.autopilot_active),
            "provider_usage": {
                "input_tokens": session.total_input_tokens,
                "output_tokens": session.total_output_tokens,
                "cached_input_tokens": session.total_cached_input_tokens,
            },
        }

    def list_sessions_snapshot(
        self,
        *,
        limit: int = 20,
        platform: str = "",
        room_id: str = "",
        user_scope: str = "",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for session in self.session_states.values():
            row_platform, row_room_id = self._session_identity(session.session_id)
            if platform and row_platform != platform:
                continue
            if room_id and row_room_id != room_id:
                continue
            if user_scope and str(session.flags.get("user_scope") or "") != user_scope:
                continue
            provider_name = session.provider_override or self.provider_router.resolve_provider_name(
                session.persona_id or self.router.default_persona_id,
                session.mode or "default",
            )
            provider = self.provider_router.providers.get(provider_name)
            rows.append(
                {
                    "session_id": session.session_id,
                    "persona_id": session.persona_id,
                    "mode": session.mode,
                    "platform": row_platform,
                    "room_id": row_room_id,
                    "flags": dict(session.flags),
                    "yolo": bool(session.yolo_enabled),
                    "provider": provider_name,
                    "model": session.model_override or self._provider_model(provider),
                    "social": self.get_social_state_snapshot(
                        session_id=session.session_id,
                        persona_id=session.persona_id,
                        mode=session.mode,
                        platform=row_platform,
                        room_id=row_room_id,
                        flags=session.flags,
                    ),
                }
            )
        rows.sort(
            key=lambda row: str(row.get("session_id") or ""),
        )
        return rows[: max(1, int(limit))]

    def get_context_cache_snapshot(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del platform, room_id
        session = self.session_states.get(session_id)
        entries = [
            entry
            for entry in self.context_cache.values()
            if entry.session_id == session_id
        ]
        total_hits = sum(int(entry.hit_count) for entry in entries)
        total_tokens_saved = sum(
            int(entry.context_tokens_estimate) * int(entry.hit_count)
            for entry in entries
        )
        return {
            "session_id": session_id,
            "persona_id": persona_id,
            "mode": mode,
            "cache_enabled": True,
            "cache_model": "stable_prefix",
            "entry_count": len(entries),
            "ttl_seconds": self.context_cache_ttl_seconds,
            "total_hits": total_hits,
            "tokens_saved_estimate": total_tokens_saved,
            "provider_cached_input_tokens": (
                int(session.total_cached_input_tokens) if session else 0
            ),
            "provider_usage": {
                "input_tokens": int(session.total_input_tokens) if session else 0,
                "output_tokens": int(session.total_output_tokens) if session else 0,
                "cached_input_tokens": (
                    int(session.total_cached_input_tokens) if session else 0
                ),
            },
            "last_cache_key": str(session.last_context_cache_key or "") if session else "",
            "last_cache_hit": bool(session.last_context_cache_hit) if session else False,
            "last_cache_reason": (
                str(session.last_context_cache_reason or "") if session else ""
            ),
            "memory_revision": (
                str(session.last_context_memory_revision or "") if session else ""
            ),
            "entries": [
                {
                    "cache_key": entry.cache_key,
                    "persona_id": entry.persona_id,
                    "mode": entry.mode,
                    "provider": entry.provider_name,
                    "model": entry.model_name,
                    "tool_manifest_digest": entry.tool_manifest_digest[:12],
                    "context_tokens_estimate": entry.context_tokens_estimate,
                    "hit_count": entry.hit_count,
                    "created_at": entry.created_at.isoformat(),
                    "last_used_at": entry.last_used_at.isoformat(),
                }
                for entry in sorted(entries, key=lambda item: item.last_used_at, reverse=True)
            ],
            "metadata": {"flags": dict(flags or {})},
        }

    def _context_cache_metrics_for_session(self, *, session_id: str) -> dict[str, Any]:
        session = self.session_states.get(session_id)
        entries = [
            entry
            for entry in self.context_cache.values()
            if entry.session_id == session_id
        ]
        total_hits = sum(int(entry.hit_count) for entry in entries)
        tokens_saved_estimate = sum(
            int(entry.context_tokens_estimate) * int(entry.hit_count)
            for entry in entries
        )
        return {
            "cache_model": "stable_prefix",
            "entry_count": len(entries),
            "total_hits": total_hits,
            "tokens_saved_estimate": tokens_saved_estimate,
            "ttl_seconds": self.context_cache_ttl_seconds,
            "provider_cached_input_tokens": (
                int(session.total_cached_input_tokens) if session else 0
            ),
            "last_cache_key": str(session.last_context_cache_key or "") if session else "",
            "last_cache_hit": bool(session.last_context_cache_hit) if session else False,
            "last_cache_reason": (
                str(session.last_context_cache_reason or "") if session else ""
            ),
        }

    def reset_context_cache(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del persona_id, mode, platform, room_id, flags
        before = len(self.context_cache)
        self._invalidate_session_context_cache(session_id=session_id)
        after = len(self.context_cache)
        return {
            "session_id": session_id,
            "cleared": max(0, before - after),
            "remaining_global_entries": after,
        }

    def get_trace_snapshot(
        self,
        *,
        session_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get trace snapshot for a session.
        
        This method returns a unified view that includes both legacy
        trace_spans and any traces collected in the snapshot.
        """
        from core.trace import TraceSnapshot

        snapshot = TraceSnapshot(session_id=session_id, max_traces=200)
        seen_span_ids: set[str] = set()
        session = self.session_states.get(session_id)

        emitter_snapshot = self.trace_emitter.get_snapshot(session_id)
        if emitter_snapshot is not None:
            for span in emitter_snapshot.get_recent(limit=max(1, min(200, int(limit)))):
                if span.span_id in seen_span_ids:
                    continue
                snapshot.add_trace(span)
                seen_span_ids.add(span.span_id)

        if session and session.trace_spans:
            bounded = max(1, min(100, int(limit)))
            for span in session.trace_spans[-bounded:]:
                if span.span_id in seen_span_ids:
                    continue
                snapshot.add_trace(span)
                seen_span_ids.add(span.span_id)

        return snapshot.to_dict()

    def get_all_traces(self) -> dict[str, Any]:
        """Get trace snapshots for all sessions.

        Returns a mapping of session_id to trace snapshot dict for all
        sessions that have trace data.
        """
        from core.trace import TraceSnapshot

        result: dict[str, Any] = {}
        session_ids = set(self.session_states.keys())
        session_ids.update(getattr(self.trace_emitter, "_snapshots", {}).keys())

        for session_id in session_ids:
            snapshot = TraceSnapshot(session_id=session_id, max_traces=200)
            seen_span_ids: set[str] = set()
            emitter_snapshot = self.trace_emitter.get_snapshot(session_id)
            if emitter_snapshot is not None:
                for span in emitter_snapshot.get_recent(limit=200):
                    if span.span_id in seen_span_ids:
                        continue
                    snapshot.add_trace(span)
                    seen_span_ids.add(span.span_id)

            session = self.session_states.get(session_id)
            if session and session.trace_spans:
                for span in session.trace_spans:
                    if span.span_id in seen_span_ids:
                        continue
                    snapshot.add_trace(span)
                    seen_span_ids.add(span.span_id)

            if snapshot.get_trace_count() > 0:
                result[session_id] = snapshot.to_dict()

        return result

    def get_presence_snapshot(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = Event(
            type="command",
            kind=EventKind.COMMAND.value,
            text="/status",
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            metadata={
                "persona_id": persona_id,
                "mode": mode,
                "flags": dict(flags or {}),
            },
        )
        session = self._get_or_create_session(event)
        persona = self.personas.by_id(session.persona_id or persona_id)
        return self._presence_payload(
            session=session,
            persona=persona,
            mode_name=session.mode or mode,
        )

    def get_providers_snapshot(self, *, session_id: str = "") -> list[dict[str, Any]]:
        return self.list_provider_status(session_id=session_id)

    def list_provider_status(self, *, session_id: str = "") -> list[dict[str, Any]]:
        auth_entries = {
            str(item.get("provider")): item
            for item in AuthStore().list_provider_summaries()
            if isinstance(item, dict)
        }
        session = self.session_states.get(session_id) if session_id else None
        active_provider = (
            session.provider_override if session and session.provider_override else ""
        )
        active_model = (
            session.model_override if session and session.model_override else ""
        )

        rows: list[dict[str, Any]] = []
        for provider_name in self.provider_router.provider_names():
            provider = self.provider_router.providers.get(provider_name)
            auth_entry = auth_entries.get(provider_name, {})
            rows.append(
                {
                    "provider": provider_name,
                    "configured": provider is not None,
                    "active": provider_name == active_provider
                    or (
                        not active_provider
                        and provider_name == self.provider_router.default_provider_name
                    ),
                    "model": (
                        active_model
                        if provider_name == active_provider and active_model
                        else self._provider_model(provider)
                    ),
                    "auth_present": bool(
                        auth_entry.get("has_api_key") or auth_entry.get("has_token")
                    ),
                    "base_url": str(auth_entry.get("base_url") or ""),
                }
            )
        return rows

    def decide_surface_response(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str,
        room_id: str,
        user_id: str,
        text: str,
        message_id: str = "",
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Runtime-owned surface response decision.

        This method moves persona name extraction and response policy from adapters
        into runtime ownership, allowing the runtime to decide which persona should
        respond based on the message text and platform facts.

        Args:
            session_id: Unique session identifier
            persona_id: Current persona ID (may be empty for auto-selection)
            mode: Current mode
            platform: Platform name (e.g., "discord")
            room_id: Room/channel identifier
            user_id: User identifier
            text: Message text
            message_id: Message identifier
            flags: Platform-specific facts (direct_mention, reply_to_bot, etc.)

        Returns:
            Dict with should_respond, reason, suggested_style, persona_id, session_id
        """
        event = Event(
            type="message",
            kind=EventKind.CHAT.value,
            text=text,
            user_id=user_id,
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            message_id=message_id,
            metadata={
                "persona_id": persona_id,
                "mode": mode,
                "flags": dict(flags or {}),
            },
        )
        session = self._get_or_create_session(event)
        active_flags = dict(flags or {})

        # Extract mentioned personas from text using runtime catalog (runtime-owned)
        text_value = str(text or "")
        text_lower = text_value.lower()
        mentioned_persona_ids = self._extract_mentioned_persona_ids_from_text(text_lower)

        # Name trigger is allowed if no channel restriction or channel is in allowed list
        name_trigger_allowed = (
            not Config.NAME_TRIGGER_CHANNELS or room_id in Config.NAME_TRIGGER_CHANNELS
        )

        # Check for recent conversation (within last 5 minutes)
        recent_conversation = False
        if session.last_response_at is not None:
            recent_conversation = (
                datetime.now(timezone.utc) - session.last_response_at
            ) < timedelta(minutes=5)

        # Auto-reply is allowed based on config and whether this is a persona message
        auto_reply_allowed = (
            bool(Config.AUTO_REPLY_ENABLED)
            and not bool(active_flags.get("is_persona_message"))
            and (
                not Config.AUTO_REPLY_CHANNELS or room_id in Config.AUTO_REPLY_CHANNELS
            )
        )

        # Global response chance for probabilistic auto-replies
        global_response_chance = float(
            getattr(Config, "GLOBAL_RESPONSE_CHANCE", 0.0) or 0.0
        )

        should_respond = False
        reason = ""
        suggested_style = ""

        ignored_users = {
            str(user_id_value).strip()
            for user_id_value in getattr(Config, "IGNORED_USERS", [])
            if str(user_id_value).strip()
        }

        if bool(active_flags.get("bot_is_muted")):
            if bool(active_flags.get("is_direct_mention")) and any(
                phrase in text_lower for phrase in ("unmute", "speak", "wake")
            ):
                should_respond = True
                reason = "unmute_request"
                suggested_style = "direct"
            else:
                should_respond = False
                reason = "muted"
                suggested_style = ""
        elif bool(active_flags.get("author_is_bot")) and not bool(
            active_flags.get("is_persona_message")
        ):
            should_respond = False
            reason = "other_bot"
            suggested_style = ""
        elif user_id in ignored_users:
            should_respond = False
            reason = "ignored_user"
            suggested_style = ""
        elif "#ignore" in text_lower:
            should_respond = False
            reason = "ignored_tag"
            suggested_style = ""
        elif bool(active_flags.get("is_direct_mention")):
            should_respond = True
            reason = "mentioned"
            suggested_style = "direct"
        elif bool(active_flags.get("is_reply_to_bot")):
            should_respond = True
            reason = "reply_to_bot"
            suggested_style = "conversational"
        elif mentioned_persona_ids and name_trigger_allowed:
            should_respond = True
            reason = (
                "multi_persona_trigger"
                if len(mentioned_persona_ids) > 1
                else "name_trigger"
            )
            suggested_style = "direct"
        elif self._is_visual_question(text_lower) and bool(
            active_flags.get("has_visual_context")
        ):
            should_respond = True
            reason = "image_question"
            suggested_style = "descriptive"
        elif recent_conversation and not bool(active_flags.get("is_persona_message")):
            should_respond = True
            reason = "conversation_context"
            suggested_style = "conversational"
        elif auto_reply_allowed and len(text_value.strip()) >= 3:
            if "?" in text_value or any(
                text_lower.startswith(prefix)
                for prefix in ("what", "why", "how", "when", "where", "who")
            ):
                should_respond = True
                reason = "question_detection"
                suggested_style = "helpful"
            elif self._deterministic_response_gate(
                session_id=session_id,
                message_id=message_id,
                text=text_value,
                probability=global_response_chance,
            ):
                should_respond = True
                reason = "auto_reply"
                suggested_style = "casual"

        selected_persona_id = ""
        if should_respond:
            if mentioned_persona_ids:
                selected_persona_id = mentioned_persona_ids[0]
            elif session.persona_id:
                selected_persona_id = session.persona_id
            else:
                selected_persona_id = self.router.select_persona(
                    event, self.personas
                ).persona_id

        return {
            "should_respond": should_respond,
            "reason": reason,
            "suggested_style": suggested_style,
            "persona_id": selected_persona_id,
            "session_id": session.session_id,
        }

    def _extract_mentioned_persona_ids_from_text(self, text_lower: str) -> list[str]:
        """Extract mentioned persona IDs from message text using runtime catalog.

        This moves persona name matching from adapters into runtime ownership,
        allowing the runtime to decide which persona is being addressed without
        adapter-side name parsing.

        Args:
            text_lower: Lowercase message text to search

        Returns:
            List of persona IDs that appear to be mentioned in the text
        """
        mentioned_ids: list[str] = []
        if not text_lower or not hasattr(self, "personas") or not self.personas:
            return mentioned_ids

        for persona in self.personas.all():
            display_name = str(getattr(persona, "display_name", "") or "").strip()
            persona_id = str(getattr(persona, "persona_id", "") or "").strip().lower()

            if not display_name or not persona_id:
                continue

            # Check for display name mention (case insensitive)
            name_lower = display_name.lower()
            if name_lower in text_lower:
                if persona_id not in mentioned_ids:
                    mentioned_ids.append(persona_id)
                continue

            # Also check for first name if display name has spaces
            if " " in name_lower:
                first_name = name_lower.split(" ")[0]
                if first_name in text_lower and len(first_name) >= 3:
                    if persona_id not in mentioned_ids:
                        mentioned_ids.append(persona_id)

        return mentioned_ids

    @staticmethod

    @staticmethod
    def _command_argument_hint(arguments_schema: dict[str, Any]) -> str:
        properties = arguments_schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            return ""
        required = arguments_schema.get("required")
        required_set = set(required) if isinstance(required, list) else set()
        parts: list[str] = []
        for name in properties.keys():
            if name in required_set:
                parts.append(f"<{name}>")
            else:
                parts.append(f"[{name}]")
        return " ".join(parts)

    def _command_status(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        persona_id = session.persona_id or str(
            event.metadata.get("persona_id") or "default"
        )
        persona = self.personas.by_id(persona_id)
        mode = session.mode or (
            self._default_mode_for_persona(persona) if persona else "default"
        )
        provider_name = (
            session.provider_override
            or self.provider_router.resolve_provider_name(persona_id, mode)
        )
        provider = self.provider_router.providers.get(provider_name)
        model = session.model_override or self._provider_model(provider)
        model_source = (
            "session_override" if session.model_override else "provider_default"
        )
        provider_source = (
            "session_override" if session.provider_override else "router_default"
        )
        mcp_servers = self._mcp_servers_snapshot()
        project_context = self._project_context_snapshot()
        status_payload = {
            "session_id": session.session_id,
            "persona": persona_id,
            "mode": mode,
            "yolo": session.yolo_enabled,
            "provider": provider_name,
            "model": model,
            "provider_source": provider_source,
            "model_source": model_source,
            "budget_remaining": max(
                0,
                int(self.tool_policy.max_tool_calls_per_turn)
                - int(session.last_tool_calls_used),
            ),
            "tool_policy": {
                "network_enabled": self.tool_policy.network_enabled,
                "dangerous_enabled": self.tool_policy.dangerous_enabled,
                "max_tool_calls_per_turn": self.tool_policy.max_tool_calls_per_turn,
            },
            "mcp_servers": mcp_servers,
            "active_flags": dict(session.flags),
            "provider_override": session.provider_override,
            "model_override": session.model_override,
            "project_context": project_context,
            "context_budget": session.context_budget.get_status() if session.context_budget else None,
            "context_cache": self._context_cache_metrics_for_session(
                session_id=session.session_id
            ),
            "pending_approvals": {
                "count": len(session.pending_tool_approvals),
                "items": list(session.pending_tool_approvals.values())[:10],
            },
            "recent_actions": [
                {
                    "action_id": record.action_id,
                    "action_type": record.action_type,
                    "tool_name": record.tool_name,
                    "outcome": record.outcome,
                    "approval_state": record.approval_state,
                    "timestamp": record.timestamp.isoformat(),
                }
                for record in session.recent_action_records[-10:]
            ],
        }

        text = (
            f"persona={status_payload['persona']} mode={status_payload['mode']} "
            f"provider={provider_name}/{model} budget_remaining={status_payload['budget_remaining']} "
            f"cached_input_tokens={status_payload['context_cache']['provider_cached_input_tokens']} "
            f"approvals_pending={status_payload['pending_approvals']['count']} "
            f"yolo={'on' if session.yolo_enabled else 'off'} "
            f"repo={'git' if project_context['is_git_repo'] else 'none'}"
        )
        return [
            TextOutput(text=text, persona_id="system"),
            StructuredOutput(kind="command_status", data=status_payload),
        ]

    def _command_context(
        self,
        *,
        event: Event,
        session: RuntimeSessionState,
        action: str,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if action == "reset":
            snapshot = self.reset_context_cache(
                session_id=session.session_id,
                persona_id=session.persona_id,
                mode=session.mode,
                platform=event.platform,
                room_id=event.room_id or "",
                flags=session.flags,
            )
            return [
                TextOutput(
                    text=f"context cache reset (cleared={snapshot['cleared']})",
                    persona_id="system",
                ),
                StructuredOutput(kind="command_context", data=snapshot),
            ]

        snapshot = self.get_context_cache_snapshot(
            session_id=session.session_id,
            persona_id=session.persona_id,
            mode=session.mode,
            platform=event.platform,
            room_id=event.room_id or "",
            flags=session.flags,
        )
        return [
            TextOutput(
                text=(
                    f"context cache entries={snapshot['entry_count']} "
                    f"hits={snapshot['total_hits']} "
                    f"tokens_saved_estimate={snapshot['tokens_saved_estimate']} "
                    f"provider_cached_input_tokens={snapshot['provider_cached_input_tokens']}"
                ),
                persona_id="system",
            ),
            StructuredOutput(kind="command_context", data=snapshot),
        ]

    @staticmethod
    def _project_context_snapshot() -> dict[str, Any]:
        root = Path.cwd().resolve()
        key_candidates = ["README.md", "AGENTS.md", "pyproject.toml"]
        key_files = [name for name in key_candidates if (root / name).exists()]
        has_git_dir = (root / ".git").exists()

        branch = ""
        dirty = None
        if has_git_dir:
            try:
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if branch_result.returncode == 0:
                    branch = branch_result.stdout.strip()

                status_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if status_result.returncode == 0:
                    dirty = bool(status_result.stdout.strip())
            except Exception:
                branch = branch or ""

        return {
            "project_root": str(root),
            "is_git_repo": bool(has_git_dir),
            "git_branch": branch,
            "git_dirty": dirty,
            "key_files": key_files,
        }

    def _command_tools(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        persona_id = session.persona_id or str(
            event.metadata.get("persona_id") or "default"
        )
        environment = event.platform
        allowed = self.tool_policy.allowed_tools(
            persona_id=persona_id, environment=environment
        )
        rows: list[dict[str, Any]] = []
        for definition in self.tool_runner.registry.definitions():
            name = definition.name
            risk = self.tool_policy.tool_risk_tiers.get(name, "safe")
            enabled = self.tool_policy.is_tool_allowed(name, allowed)
            rows.append(
                {
                    "name": name,
                    "risk_tier": risk,
                    "enabled": enabled,
                    "source": str(definition.metadata.get("origin") or "builtin"),
                }
            )

        lines = ["Available tools:"]
        for row in rows:
            lines.append(
                f"- {row['name']} | risk={row['risk_tier']} | enabled={str(row['enabled']).lower()}"
            )
        return [
            TextOutput(text="\n".join(lines), persona_id="system"),
            StructuredOutput(kind="command_tools", data={"tools": rows}),
        ]

    def _command_trace(
        self,
        session: RuntimeSessionState,
        limit: int,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        bounded = max(1, min(100, int(limit)))
        spans = session.trace_spans[-bounded:]
        items: list[dict[str, Any]] = []
        for span in spans:
            safe_data = dict(span.data)
            safe_data.pop("args", None)
            safe_data.pop("output", None)
            safe_data.pop("content", None)
            items.append(
                {
                    "trace_type": span.trace_type,
                    "session_id": span.session_id,
                    "span_id": span.span_id,
                    "parent_span_id": span.parent_span_id,
                    "start_ts": span.start_ts.isoformat(),
                    "end_ts": span.end_ts.isoformat(),
                    "data": safe_data,
                }
            )
        return [
            StructuredOutput(
                kind="command_trace",
                data={
                    "session_id": session.session_id,
                    "count": len(items),
                    "spans": items,
                },
            ),
            TextOutput(
                text=f"trace spans: {len(items)} (session={session.session_id})",
                persona_id="system",
            ),
        ]

    async def _command_recap(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        persona_id = session.persona_id or str(
            event.metadata.get("persona_id") or "default"
        )
        namespace = MemoryNamespace(
            persona_id=persona_id,
            room_id=event.room_id or "default",
        )
        memory_context = await self.memory_manager.load_context(
            namespace=namespace, limit=12
        )
        recent = [
            str(message.get("content") or "")
            for message in memory_context.recent_history[-6:]
            if isinstance(message, dict)
        ]
        if memory_context.summary.strip():
            recap_text = memory_context.summary.strip()
        else:
            recap_text = "\n".join([line for line in recent if line])
        if not recap_text.strip():
            recap_text = "No conversation history available for this session yet."
        return [
            TextOutput(text=recap_text, persona_id="system"),
            StructuredOutput(
                kind="command_recap",
                data={
                    "session_id": session.session_id,
                    "summary": memory_context.summary,
                    "message_count": len(memory_context.recent_history),
                },
            ),
        ]

    async def _command_eval(
        self,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "pytest",
            "tests/scenarios",
            "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        out = (stdout or b"").decode("utf-8", errors="replace")
        err = (stderr or b"").decode("utf-8", errors="replace")
        code = int(process.returncode or 0)
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        last_line = lines[-1] if lines else ""
        passed = "passed" in last_line and "failed" not in last_line
        summary = {
            "session_id": session.session_id,
            "return_code": code,
            "passed": passed and code == 0,
            "summary_line": last_line,
            "stderr_summary": (err.splitlines()[-1] if err.splitlines() else ""),
        }
        text = "eval passed" if summary["passed"] else "eval failed"
        return [
            TextOutput(text=text, persona_id="system"),
            StructuredOutput(kind="command_eval", data=summary),
        ]

    async def _command_continue(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not session.autopilot_active:
            return [
                ErrorOutput(
                    code="AUTOPILOT_NOT_ACTIVE",
                    message="No active autopilot plan.",
                    hint="Run /autopilot --steps <n> first.",
                )
            ]
        return await self._autopilot_run_next_checkpoint(event=event, session=session)

    def _command_stop(
        self,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        session.autopilot_active = False
        session.autopilot_plan = []
        session.autopilot_index = 0
        session.autopilot_last_decision = "stopped"
        return [
            TextOutput(text="autopilot stopped", persona_id="system"),
            StructuredOutput(
                kind="autopilot_stop",
                data={"session_id": session.session_id, "status": "stopped"},
            ),
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.autopilot",
                    "new": "stopped",
                },
            ),
        ]

    def _command_mode(
        self,
        mode_name: str,
        event: Event,
        session: RuntimeSessionState,
    ) -> tuple[
        list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
        list[StateMutation],
    ]:
        persona_id = session.persona_id or str(
            event.metadata.get("persona_id") or "default"
        )
        persona = self.personas.by_id(persona_id)
        if persona is None:
            return [
                ErrorOutput(
                    code="PERSONA_NOT_FOUND",
                    message=f"Persona '{persona_id}' was not found.",
                    hint="Set a valid persona and retry.",
                )
            ], []

        available_modes = self._available_modes_for_persona(persona)
        if not mode_name or mode_name not in available_modes:
            return [
                ErrorOutput(
                    code="INVALID_MODE",
                    message=f"Invalid mode '{mode_name}'.",
                    hint=f"Available modes: {', '.join(sorted(available_modes))}",
                )
            ], []

        old_mode = session.mode
        session.mode = mode_name
        mutation = StateMutation(
            path=f"session:{session.session_id}.mode",
            old=old_mode,
            new=mode_name,
        )
        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            TextOutput(
                text=f"mode switched to {mode_name}",
                persona_id="system",
            ),
            StructuredOutput(
                kind="command_mode",
                data={
                    "persona": persona_id,
                    "mode": mode_name,
                    "available_modes": sorted(available_modes),
                },
            ),
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": mutation.path,
                    "old": mutation.old,
                    "new": mutation.new,
                },
            ),
        ]
        return outputs, [mutation]

    def _command_yolo(
        self,
        session: RuntimeSessionState,
        state: str,
        confirm: bool,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not state:
            status = "on" if session.yolo_enabled else "off"
            return [
                TextOutput(text=f"yolo is {status}", persona_id="system"),
                StructuredOutput(
                    kind="command_yolo",
                    data={
                        "session_id": session.session_id,
                        "enabled": session.yolo_enabled,
                    },
                ),
            ]
        if state not in {"on", "off"}:
            return [
                ErrorOutput(
                    code="INVALID_YOLO_STATE",
                    message=f"Invalid yolo state '{state}'.",
                    hint="Usage: /yolo [on|off]",
                )
            ]

        if state == "on" and not confirm:
            return [
                TextOutput(
                    text=(
                        "yolo enable requires explicit confirmation. "
                        "Run /yolo on --confirm to enable."
                    ),
                    persona_id="system",
                ),
                StructuredOutput(
                    kind="confirmation_required",
                    data={
                        "action_type": "yolo_enable",
                        "mode": "confirm",
                        "description": "Enable YOLO mode",
                        "hint": "Run /yolo on --confirm",
                    },
                ),
            ]
        old_value = session.yolo_enabled
        session.yolo_enabled = state == "on"
        return [
            TextOutput(
                text=f"yolo {state}",
                persona_id="system",
            ),
            StructuredOutput(
                kind="command_yolo",
                data={
                    "session_id": session.session_id,
                    "enabled": session.yolo_enabled,
                },
            ),
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.yolo",
                    "old": old_value,
                    "new": session.yolo_enabled,
                },
            ),
        ]

    def _command_persona(
        self,
        session: RuntimeSessionState,
        name: str,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not name:
            return [
                TextOutput(
                    text=f"persona is {session.persona_id}",
                    persona_id="system",
                ),
                StructuredOutput(
                    kind="command_persona",
                    data={
                        "session_id": session.session_id,
                        "persona": session.persona_id,
                    },
                ),
            ]

        persona = self.personas.by_id(name)
        if persona is None:
            return [
                ErrorOutput(
                    code="PERSONA_NOT_FOUND",
                    message=f"Persona '{name}' was not found.",
                    hint="Use a persona id from your catalog.",
                )
            ]

        old_persona = session.persona_id
        session.persona_id = persona.persona_id
        session.mode = self._default_mode_for_persona(persona)
        return [
            TextOutput(
                text=f"persona switched to {persona.persona_id}", persona_id="system"
            ),
            StructuredOutput(
                kind="command_persona",
                data={
                    "session_id": session.session_id,
                    "persona": session.persona_id,
                    "mode": session.mode,
                },
            ),
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.persona",
                    "old": old_persona,
                    "new": session.persona_id,
                },
            ),
        ]

    def _command_model(
        self,
        session: RuntimeSessionState,
        spec: str,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not spec:
            provider_name = (
                session.provider_override
                or self.provider_router.resolve_provider_name(session.persona_id, session.mode)
            )
            provider = self.provider_router.providers.get(provider_name)
            model = session.model_override or self._provider_model(provider)
            source = (
                "session_override" if session.model_override else "provider_default"
            )
            return [
                TextOutput(
                    text=f"model is {provider_name}/{model} ({source})",
                    persona_id="system",
                ),
                StructuredOutput(
                    kind="command_model",
                    data={
                        "session_id": session.session_id,
                        "provider": provider_name,
                        "model": model,
                        "source": source,
                    },
                ),
            ]

        if spec.lower() == "reset":
            old_provider = session.provider_override
            old_model = session.model_override
            session.provider_override = ""
            session.model_override = ""
            return [
                TextOutput(text="model override reset", persona_id="system"),
                StructuredOutput(
                    kind="command_model",
                    data={
                        "session_id": session.session_id,
                        "provider_override": "",
                        "model_override": "",
                        "source": "provider_default",
                    },
                ),
                self._build_span_trace(
                    trace_type="state",
                    session_id=session.session_id,
                    data={
                        "path": f"session:{session.session_id}.model_override",
                        "old": {"provider": old_provider, "model": old_model},
                        "new": {"provider": "", "model": ""},
                    },
                ),
            ]

        if "/" not in spec:
            return [
                ErrorOutput(
                    code="INVALID_MODEL_SPEC",
                    message="Model spec must use provider/model format.",
                    hint="Usage: /model openai/gpt-4o-mini",
                )
            ]

        provider_name, model_name = spec.split("/", 1)
        provider_name = canonical_provider_name(provider_name.strip().lower())
        model_name = model_name.strip()
        if provider_name not in self.provider_router.providers:
            return [
                ErrorOutput(
                    code="UNKNOWN_PROVIDER",
                    message=f"Unknown provider '{provider_name}'.",
                    hint=f"Available: {', '.join(self.provider_router.provider_names())}",
                )
            ]
        if not model_name:
            return [
                ErrorOutput(
                    code="MODEL_REQUIRED",
                    message="Model name is required.",
                    hint="Usage: /model provider/model",
                )
            ]

        provider = self.provider_router.providers[provider_name]
        if not self._provider_accepts_model(provider=provider, model_name=model_name):
            return [
                ErrorOutput(
                    code="INVALID_PROVIDER_MODEL",
                    message=f"Model '{model_name}' is not accepted by provider '{provider_name}'.",
                    hint="Run /models <provider> to inspect known options.",
                )
            ]

        old_provider = session.provider_override
        old_model = session.model_override
        session.provider_override = provider_name
        session.model_override = model_name
        return [
            TextOutput(
                text=f"model override set to {provider_name}/{model_name}",
                persona_id="system",
            ),
            StructuredOutput(
                kind="command_model",
                data={
                    "session_id": session.session_id,
                    "provider_override": provider_name,
                    "model_override": model_name,
                    "source": "session_override",
                },
            ),
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.model_override",
                    "old": {"provider": old_provider, "model": old_model},
                    "new": {"provider": provider_name, "model": model_name},
                },
            ),
        ]

    def _command_models(
        self,
        session: RuntimeSessionState,
        provider_name: str,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        selected = canonical_provider_name(
            provider_name
        ) or self.provider_router.resolve_provider_name(session.persona_id, session.mode)
        if selected not in self.provider_router.providers:
            return [
                ErrorOutput(
                    code="UNKNOWN_PROVIDER",
                    message=f"Unknown provider '{selected}'.",
                    hint=f"Available: {', '.join(self.provider_router.provider_names())}",
                )
            ]
        provider = self.provider_router.providers[selected]
        models = self._provider_known_models(provider)
        if not models:
            fallback = self._provider_model(provider)
            models = [fallback] if fallback != "unknown" else []
        return [
            TextOutput(
                text=(
                    f"models for {selected}: {', '.join(models)}"
                    if models
                    else f"models for {selected}: unknown"
                ),
                persona_id="system",
            ),
            StructuredOutput(
                kind="command_models",
                data={
                    "session_id": session.session_id,
                    "provider": selected,
                    "models": models,
                },
            ),
        ]

    async def _command_shell(
        self,
        event: Event,
        session: RuntimeSessionState,
        command: str,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not command.strip():
            return [
                ErrorOutput(
                    code="SHELL_COMMAND_REQUIRED",
                    message="Shell command is required.",
                    hint="Usage: /shell --command 'ls -la'",
                )
            ]
        requested_calls = [
            ToolCall(
                name="shell_exec",
                arguments={
                    "command": command,
                    "allow_dangerous": bool(self.tool_policy.dangerous_enabled),
                },
            )
        ]
        executable_calls, gated_results, gated_trace_dicts, approval_outputs = (
            await self._partition_tool_calls_for_approval(
                event=event,
                session=session,
                tool_calls=requested_calls,
            )
        )
        results = list(gated_results)
        trace_dicts = list(gated_trace_dicts)
        if executable_calls:
            runner_results, runner_trace_dicts = await self.tool_runner.execute_with_trace(
                persona_id=session.persona_id,
                environment=event.platform,
                tool_calls=executable_calls,
            )
            results.extend(runner_results)
            trace_dicts.extend(runner_trace_dicts)
            await self._record_tool_results(
                event=event,
                session=session,
                results=runner_results,
            )
        result = (
            results[0]
            if results
            else ToolResult(name="shell_exec", error="No shell result available")
        )
        trace_outputs = [
            self._build_span_trace(
                trace_type=str(item.get("trace_type") or "tool"),
                session_id=session.session_id,
                data=item,
            )
            for item in trace_dicts
        ]

        if result.error:
            return [
                ErrorOutput(
                    code="SHELL_EXEC_ERROR",
                    message=result.error,
                    hint="Check tool policy and command safety.",
                ),
                *approval_outputs,
                *trace_outputs,
            ]

        payload = self._parse_shell_payload(result.output)
        if payload is None:
            return [
                TextOutput(text=result.output, persona_id="system"),
                StructuredOutput(
                    kind="command_shell",
                    data={
                        "output": result.output,
                    },
                ),
                *trace_outputs,
            ]

        label = "ok" if int(payload.get("exit_code", 1)) == 0 else "error"
        text = f"shell {label} (exit={int(payload.get('exit_code', 1))})" + (
            " [truncated]" if bool(payload.get("truncated", False)) else ""
        )
        return [
            TextOutput(text=text, persona_id="system"),
            StructuredOutput(kind="command_shell", data=payload),
            *trace_outputs,
        ]

    async def _command_autopilot(
        self,
        event: Event,
        session: RuntimeSessionState,
        steps: int,
        confirm: bool,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        bounded_steps = max(3, min(7, int(steps)))
        max_steps_flag = session.flags.get("max_steps")
        if isinstance(max_steps_flag, int):
            bounded_steps = min(bounded_steps, max_steps_flag)

        session.autopilot_plan = [
            f"checkpoint-{i}" for i in range(1, bounded_steps + 1)
        ]
        session.autopilot_index = 0
        session.autopilot_active = True
        session.autopilot_last_decision = "planned"

        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            StructuredOutput(
                kind="autopilot_plan",
                data={
                    "steps": bounded_steps,
                    "checkpoints": list(session.autopilot_plan),
                    "requires_confirm": True,
                    "status": "planned",
                },
            )
        ]
        outputs.append(
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.autopilot",
                    "new": "planned",
                    "steps": bounded_steps,
                },
            )
        )

        if not confirm and not session.yolo_enabled:
            outputs.append(
                TextOutput(
                    text=(
                        f"autopilot plan prepared ({bounded_steps} steps). "
                        "run /continue to execute next checkpoint or /stop to cancel."
                    ),
                    persona_id="system",
                )
            )
            return outputs
        outputs.extend(
            await self._autopilot_run_next_checkpoint(event=event, session=session)
        )
        return outputs

    @staticmethod
    def _resolve_project_path(path_text: str) -> tuple[Path, Path] | ErrorOutput:
        path_value = path_text.strip()
        if not path_value:
            return ErrorOutput(
                code="PATH_REQUIRED",
                message="File path is required.",
                hint="Usage: /diff --path <relative-path> --content '<text>'",
            )

        project_root = Path.cwd().resolve()
        candidate = (project_root / path_value).resolve()
        try:
            candidate.relative_to(project_root)
        except ValueError:
            return ErrorOutput(
                code="PATH_OUT_OF_ROOT",
                message="Path outside project root is not allowed.",
                hint="Use a path inside the current project directory.",
            )
        return project_root, candidate

    def _command_diff_preview(
        self,
        *,
        session: RuntimeSessionState,
        path: str,
        new_content: str,
    ) -> tuple[
        list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
        list[StateMutation],
    ]:
        if not new_content:
            return [
                ErrorOutput(
                    code="CONTENT_REQUIRED",
                    message="Diff content is required.",
                    hint="Usage: /diff --path <relative-path> --content '<text>'",
                )
            ], []

        resolved = self._resolve_project_path(path)
        if isinstance(resolved, ErrorOutput):
            return [resolved], []
        project_root, candidate = resolved

        old_content = ""
        if candidate.exists():
            old_content = candidate.read_text(encoding="utf-8", errors="replace")
        is_new_file = not candidate.exists()

        diff_lines = list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(candidate.relative_to(project_root)),
                tofile=str(candidate.relative_to(project_root)),
                lineterm="",
            )
        )
        unified_diff = "".join(diff_lines) if diff_lines else "(no changes)"
        relative_path = str(candidate.relative_to(project_root))

        if session.yolo_enabled and is_new_file:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(new_content, encoding="utf-8")
            outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
                TextOutput(
                    text=(
                        f"yolo fast-path applied new file {relative_path} "
                        "without confirmation"
                    ),
                    persona_id="system",
                ),
                StructuredOutput(
                    kind="diff_applied",
                    data={
                        "confirmation_id": "",
                        "file_path": relative_path,
                        "yolo_bypass": True,
                    },
                ),
            ]
            return outputs, []

        confirmation_id = uuid.uuid4().hex[:8]
        session.pending_diffs[confirmation_id] = {
            "path": relative_path,
            "new_content": new_content,
            "preview": unified_diff,
        }

        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            TextOutput(
                text=(
                    f"diff preview queued for {relative_path} (id={confirmation_id}). "
                    f"Run /apply {confirmation_id} or /reject {confirmation_id}."
                ),
                persona_id="system",
            ),
            StructuredOutput(
                kind="diff_preview",
                data={
                    "confirmation_id": confirmation_id,
                    "file_path": relative_path,
                    "unified_diff": unified_diff,
                },
            ),
            StructuredOutput(
                kind="confirmation_required",
                data={
                    "confirmation_id": confirmation_id,
                    "action_type": "file_write",
                    "mode": "confirm",
                    "description": f"Apply pending update to {relative_path}",
                    "preview": unified_diff,
                },
            ),
        ]
        mutations = [
            StateMutation(
                path=f"session:{session.session_id}.pending_diffs",
                old=None,
                new={"queued": confirmation_id, "path": relative_path},
            )
        ]
        return outputs, mutations

    def _command_apply_diff(
        self,
        *,
        session: RuntimeSessionState,
        confirmation_id: str,
    ) -> tuple[
        list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
        list[StateMutation],
    ]:
        key = confirmation_id.strip()
        if not key:
            return [
                ErrorOutput(
                    code="CONFIRMATION_ID_REQUIRED",
                    message="Confirmation id is required.",
                    hint="Usage: /apply <id>",
                )
            ], []

        pending = session.pending_diffs.get(key)
        if pending is None:
            return [
                ErrorOutput(
                    code="CONFIRMATION_NOT_FOUND",
                    message=f"No pending confirmation '{key}'.",
                    hint="Run /help or queue a new /diff preview.",
                )
            ], []

        resolved = self._resolve_project_path(str(pending.get("path") or ""))
        if isinstance(resolved, ErrorOutput):
            return [resolved], []
        _, candidate = resolved

        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(str(pending.get("new_content") or ""), encoding="utf-8")
        session.pending_diffs.pop(key, None)

        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            TextOutput(
                text=f"applied diff {key} to {pending.get('path')}", persona_id="system"
            ),
            StructuredOutput(
                kind="diff_applied",
                data={"confirmation_id": key, "file_path": pending.get("path")},
            ),
        ]
        mutations = [
            StateMutation(
                path=f"session:{session.session_id}.pending_diffs",
                old={"queued": key},
                new={"applied": key},
            )
        ]
        return outputs, mutations

    def _command_reject_diff(
        self,
        *,
        session: RuntimeSessionState,
        confirmation_id: str,
    ) -> tuple[
        list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
        list[StateMutation],
    ]:
        key = confirmation_id.strip()
        if not key:
            return [
                ErrorOutput(
                    code="CONFIRMATION_ID_REQUIRED",
                    message="Confirmation id is required.",
                    hint="Usage: /reject <id>",
                )
            ], []

        pending = session.pending_diffs.pop(key, None)
        if pending is None:
            return [
                ErrorOutput(
                    code="CONFIRMATION_NOT_FOUND",
                    message=f"No pending confirmation '{key}'.",
                    hint="Run /help or queue a new /diff preview.",
                )
            ], []

        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            TextOutput(text=f"rejected diff {key}", persona_id="system"),
            StructuredOutput(
                kind="diff_rejected",
                data={"confirmation_id": key, "file_path": pending.get("path")},
            ),
        ]
        mutations = [
            StateMutation(
                path=f"session:{session.session_id}.pending_diffs",
                old={"queued": key},
                new={"rejected": key},
            )
        ]
        return outputs, mutations

    async def _autopilot_run_next_checkpoint(
        self,
        event: Event,
        session: RuntimeSessionState,
    ) -> list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput]:
        if not session.autopilot_active:
            return [
                ErrorOutput(
                    code="AUTOPILOT_NOT_ACTIVE",
                    message="No active autopilot plan.",
                    hint="Run /autopilot --steps <n> first.",
                )
            ]

        total = len(session.autopilot_plan)
        if session.autopilot_index >= total:
            session.autopilot_active = False
            return [
                TextOutput(
                    text=f"autopilot completed {total} checkpoints",
                    persona_id="system",
                )
            ]

        checkpoint_number = session.autopilot_index + 1
        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput] = [
            StructuredOutput(
                kind="autopilot_checkpoint",
                data={
                    "checkpoint": checkpoint_number,
                    "total": total,
                    "approved": True,
                    "status": "running",
                },
            )
        ]

        dry_run = bool(session.flags.get("dry_run", False))
        if dry_run:
            outputs.append(
                TextOutput(
                    text=f"checkpoint {checkpoint_number}: dry-run, no execution",
                    persona_id="system",
                )
            )
            decision = self._reflect_autopilot_step(tool_results=[])
            session.autopilot_last_decision = decision
            session.autopilot_index += 1
            outputs.append(
                self._build_span_trace(
                    trace_type="state",
                    session_id=session.session_id,
                    data={
                        "path": f"session:{session.session_id}.autopilot.decision",
                        "checkpoint": checkpoint_number,
                        "decision": decision,
                    },
                )
            )
            outputs.append(
                TextOutput(
                    text=(
                        "run /continue for next checkpoint"
                        if session.autopilot_index < total
                        else "autopilot checkpoints finished"
                    ),
                    persona_id="system",
                )
            )
            if session.autopilot_index >= total:
                session.autopilot_active = False
            return outputs

        tick_event = Event(
            type="tick",
            kind=EventKind.SYSTEM.value,
            text="",
            user_id=event.user_id,
            room_id=event.room_id,
            platform=event.platform,
            session_id=event.session_id,
            metadata={
                "persona_id": session.persona_id,
                "mode": session.mode,
                "flags": dict(session.flags),
            },
        )
        tick_response, tick_traces = await self._run_chat_flow(tick_event, session)
        outputs.append(
            TextOutput(
                text=f"checkpoint {checkpoint_number}: {tick_response.text}",
                persona_id=tick_response.persona_id,
            )
        )
        outputs.extend(tick_traces)

        tool_results = tick_response.metadata.get("tool_results")
        decision = self._reflect_autopilot_step(
            tool_results=tool_results if isinstance(tool_results, list) else []
        )
        session.autopilot_last_decision = decision
        outputs.append(
            self._build_span_trace(
                trace_type="state",
                session_id=session.session_id,
                data={
                    "path": f"session:{session.session_id}.autopilot.decision",
                    "checkpoint": checkpoint_number,
                    "decision": decision,
                },
            )
        )

        if decision == "stop":
            session.autopilot_active = False
            outputs.append(
                TextOutput(text="autopilot stopped by reflection", persona_id="system")
            )
            return outputs

        if decision == "retry":
            outputs.append(
                TextOutput(
                    text="reflection requested retry; run /continue to retry checkpoint",
                    persona_id="system",
                )
            )
            return outputs

        session.autopilot_index += 1
        if session.autopilot_index >= total:
            session.autopilot_active = False
            outputs.append(
                TextOutput(
                    text=f"autopilot completed {total} checkpoints", persona_id="system"
                )
            )
        else:
            outputs.append(
                TextOutput(
                    text="run /continue for next checkpoint", persona_id="system"
                )
            )
        return outputs

    @staticmethod
    def _reflect_autopilot_step(tool_results: list[dict[str, Any]]) -> str:
        for result in tool_results:
            if isinstance(result, dict) and result.get("error"):
                return "retry"
        return "continue"

    def _context_cache_key(
        self,
        *,
        session_id: str,
        persona_id: str,
        mode: str,
        provider_name: str,
        model_name: str,
    ) -> str:
        return (
            f"{session_id}:{persona_id}:{mode or 'default'}:"
            f"{provider_name}:{model_name or 'default'}"
        )

    @staticmethod
    def _context_signature(
        *,
        persona_id: str,
        mode_name: str,
        provider_name: str,
        model_name: str,
        tool_manifest_digest: str,
    ) -> str:
        payload = {
            "persona_id": persona_id,
            "mode_name": mode_name,
            "provider_name": provider_name,
            "model_name": model_name,
            "tool_manifest_digest": tool_manifest_digest,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _estimate_messages_tokens(messages: list[ProviderMessage]) -> int:
        total = 0
        for message in messages:
            total += len(str(message.content or "").split())
        return total

    @staticmethod
    def _tool_manifest_digest(tool_schemas: list[dict[str, Any]]) -> str:
        raw = json.dumps(tool_schemas, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_provider_usage(
        *,
        response: Any,
        request_messages: list[ProviderMessage],
        response_text: str,
    ) -> ProviderUsage:
        usage = getattr(response, "usage", ProviderUsage())
        if not isinstance(usage, ProviderUsage):
            usage = ProviderUsage()
        input_tokens = int(usage.input_tokens or 0)
        output_tokens = int(usage.output_tokens or 0)
        cached_input_tokens = int(usage.cached_input_tokens or 0)
        if input_tokens <= 0:
            input_tokens = GestaltRuntime._estimate_messages_tokens(request_messages)
        if output_tokens <= 0 and response_text.strip():
            output_tokens = len(response_text.split())
        return ProviderUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=min(cached_input_tokens, input_tokens),
        )

    @staticmethod
    def _merge_provider_usage(*items: ProviderUsage) -> ProviderUsage:
        merged = ProviderUsage()
        for item in items:
            merged.input_tokens += int(item.input_tokens or 0)
            merged.output_tokens += int(item.output_tokens or 0)
            merged.cached_input_tokens += int(item.cached_input_tokens or 0)
        return merged

    @staticmethod
    def _record_session_provider_usage(
        *,
        session: RuntimeSessionState,
        usage: ProviderUsage,
    ) -> None:
        session.total_input_tokens += int(usage.input_tokens or 0)
        session.total_output_tokens += int(usage.output_tokens or 0)
        session.total_cached_input_tokens += int(usage.cached_input_tokens or 0)

    def _prune_context_cache(self) -> None:
        if len(self.context_cache) <= self.context_cache_max_entries:
            return
        ordered = sorted(
            self.context_cache.items(),
            key=lambda item: item[1].last_used_at,
        )
        overflow = len(self.context_cache) - self.context_cache_max_entries
        for key, _entry in ordered[:overflow]:
            self.context_cache.pop(key, None)

    def _prune_session_context_cache(self, *, session_id: str) -> None:
        session_entries = [
            entry
            for entry in self.context_cache.values()
            if entry.session_id == session_id
        ]
        if len(session_entries) <= self.context_cache_max_per_session:
            return
        ordered = sorted(session_entries, key=lambda entry: entry.last_used_at)
        overflow = len(session_entries) - self.context_cache_max_per_session
        for entry in ordered[:overflow]:
            self.context_cache.pop(entry.cache_key, None)

    def _invalidate_session_context_cache(self, *, session_id: str) -> None:
        stale_keys = [
            cache_key
            for cache_key, entry in self.context_cache.items()
            if entry.session_id == session_id
        ]
        for cache_key in stale_keys:
            self.context_cache.pop(cache_key, None)

    async def _build_provider_messages_with_cache(
        self,
        *,
        session: RuntimeSessionState,
        persona: PersonaDefinition,
        memory_context: MemoryContextBundle,
        rag_context: str,
        mode_name: str,
        provider_name: str,
        model_name: str,
        tool_schemas: list[dict[str, Any]],
    ) -> tuple[list[ProviderMessage], TraceOutput, ProviderRequestHints]:
        now = datetime.now(timezone.utc)
        tool_manifest_digest = self._tool_manifest_digest(tool_schemas)
        cache_key = self._context_cache_key(
            session_id=session.session_id,
            persona_id=persona.persona_id,
            mode=mode_name,
            provider_name=provider_name,
            model_name=model_name,
        )
        signature = self._context_signature(
            persona_id=persona.persona_id,
            mode_name=mode_name,
            provider_name=provider_name,
            model_name=model_name,
            tool_manifest_digest=tool_manifest_digest,
        )
        cache_entry = self.context_cache.get(cache_key)
        cache_hit = False
        tokens_saved_estimate = 0
        reason = "miss"
        dynamic_context_prompt = self.persona_engine.build_runtime_context_prompt(
            summary=memory_context.summary,
            rag_context=rag_context,
            facts=memory_context.facts,
            persona_state=memory_context.persona_state,
        )
        dynamic_messages: list[ProviderMessage] = []
        if dynamic_context_prompt:
            dynamic_messages.append(
                ProviderMessage(role="system", content=dynamic_context_prompt)
            )

        if cache_entry is not None:
            expired = (now - cache_entry.last_used_at) > timedelta(
                seconds=self.context_cache_ttl_seconds
            )
            if not expired and cache_entry.signature == signature:
                cache_hit = True
                cache_entry.last_used_at = now
                cache_entry.hit_count += 1
                reason = "stable_prefix_match"
                tokens_saved_estimate = int(cache_entry.context_tokens_estimate)
                provider_messages = [
                    ProviderMessage(
                        role=str(item.get("role") or "user"),
                        content=str(item.get("content") or ""),
                    )
                    for item in cache_entry.stable_prefix_messages
                    if str(item.get("content") or "")
                ]
                provider_messages.extend(dynamic_messages)
                for message in memory_context.recent_history:
                    role = str(message.get("role") or "user")
                    content = str(message.get("content") or "")
                    if content:
                        provider_messages.append(
                            ProviderMessage(role=role, content=content)
                        )
                session.last_context_cache_key = cache_key
                session.last_context_cache_hit = True
                session.last_context_cache_reason = reason
                session.last_context_memory_revision = memory_context.revision
                trace = self._build_span_trace(
                    trace_type="context_cache",
                    session_id=session.session_id,
                    data={
                        "cache_hit": True,
                        "cache_key": cache_key,
                        "cache_reason": reason,
                        "cache_scope": "stable_prefix",
                        "memory_revision": memory_context.revision[:12],
                        "provider": provider_name,
                        "model": model_name,
                        "tool_manifest_digest": tool_manifest_digest[:12],
                        "prefix_token_estimate": tokens_saved_estimate,
                        "tokens_saved_estimate": tokens_saved_estimate,
                        "cache_size": len(self.context_cache),
                    },
                )
                return (
                    provider_messages,
                    trace,
                    ProviderRequestHints(
                        cache_key=cache_key,
                        prefix_token_estimate=tokens_saved_estimate,
                        allow_provider_prefix_cache=True,
                    ),
                )
            reason = "expired" if expired else "signature_mismatch"

        core_system_prompt = self.persona_engine.build_core_system_prompt(persona)
        core_system_prompt = self._inject_mode_prompt(
            persona=persona,
            base_prompt=core_system_prompt,
            mode_name=mode_name,
        )
        provider_messages = [ProviderMessage(role="system", content=core_system_prompt)]
        provider_messages.extend(dynamic_messages)
        for message in memory_context.recent_history:
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "")
            if content:
                provider_messages.append(ProviderMessage(role=role, content=content))

        context_tokens = self._estimate_messages_tokens(
            [ProviderMessage(role="system", content=core_system_prompt)]
        )
        self.context_cache[cache_key] = ContextCacheEntry(
            cache_key=cache_key,
            session_id=session.session_id,
            persona_id=persona.persona_id,
            mode=mode_name,
            provider_name=provider_name,
            model_name=model_name,
            tool_manifest_digest=tool_manifest_digest,
            signature=signature,
            stable_prefix_messages=[
                {"role": "system", "content": core_system_prompt},
            ],
            context_tokens_estimate=context_tokens,
            created_at=now,
            last_used_at=now,
            hit_count=0,
        )
        self._prune_session_context_cache(session_id=session.session_id)
        self._prune_context_cache()
        session.last_context_cache_key = cache_key
        session.last_context_cache_hit = False
        session.last_context_cache_reason = reason
        session.last_context_memory_revision = memory_context.revision

        trace = self._build_span_trace(
            trace_type="context_cache",
            session_id=session.session_id,
            data={
                "cache_hit": cache_hit,
                "cache_key": cache_key,
                "cache_reason": reason,
                "cache_scope": "stable_prefix",
                "memory_revision": memory_context.revision[:12],
                "provider": provider_name,
                "model": model_name,
                "tool_manifest_digest": tool_manifest_digest[:12],
                "prefix_token_estimate": context_tokens,
                "tokens_saved_estimate": tokens_saved_estimate,
                "cache_size": len(self.context_cache),
            },
        )
        return (
            provider_messages,
            trace,
            ProviderRequestHints(
                cache_key=cache_key,
                prefix_token_estimate=context_tokens,
                allow_provider_prefix_cache=True,
            ),
        )

    def _get_or_create_session(self, event: Event) -> RuntimeSessionState:
        existing = self.session_states.get(event.session_id)
        if existing is not None:
            return existing

        persona_id = str(
            event.metadata.get("persona_id") or self.router.default_persona_id
        )
        persona = self.personas.by_id(persona_id)
        mode = self._default_mode_for_persona(persona) if persona else "default"
        initial_flags: dict[str, Any] = {}
        incoming_flags = event.metadata.get("flags")
        if isinstance(incoming_flags, dict):
            initial_flags.update(incoming_flags)
        yolo_enabled = bool(initial_flags.get("yolo", False))
        created = RuntimeSessionState(
            session_id=event.session_id,
            persona_id=persona_id,
            mode=mode,
            flags=initial_flags,
            yolo_enabled=yolo_enabled,
            context_budget=ContextBudget.from_env(),
        )
        self.session_states[event.session_id] = created
        
        # Emit session lifecycle trace
        session_span_id = str(uuid.uuid4())
        self.trace_emitter.emit_session_start(
            session_id=event.session_id,
            span_id=session_span_id,
            data={
                "persona_id": persona_id,
                "mode": mode,
                "platform": event.platform,
                "room_id": event.room_id or "default",
            },
        )
        
        return created

    def _apply_event_metadata(
        self,
        session: RuntimeSessionState,
        event: Event,
    ) -> list[StateMutation]:
        mutations: list[StateMutation] = []
        invalidate_context_cache = False

        incoming_persona = str(event.metadata.get("persona_id") or "").strip().lower()
        if incoming_persona and incoming_persona != session.persona_id:
            mutations.append(
                StateMutation(
                    path=f"session:{session.session_id}.persona",
                    old=session.persona_id,
                    new=incoming_persona,
                )
            )
            session.persona_id = incoming_persona
            invalidate_context_cache = True

        incoming_mode = str(event.metadata.get("mode") or "").strip()
        if incoming_mode and incoming_mode != session.mode:
            mutations.append(
                StateMutation(
                    path=f"session:{session.session_id}.mode",
                    old=session.mode,
                    new=incoming_mode,
                )
            )
            session.mode = incoming_mode
            invalidate_context_cache = True

        incoming_flags = event.metadata.get("flags")
        if isinstance(incoming_flags, dict):
            old_flags = dict(session.flags)
            session.flags.update(incoming_flags)
            if "yolo" in incoming_flags:
                session.yolo_enabled = bool(incoming_flags.get("yolo"))
            if session.flags != old_flags:
                mutations.append(
                    StateMutation(
                        path=f"session:{session.session_id}.flags",
                        old=old_flags,
                        new=dict(session.flags),
                    )
                )
        if invalidate_context_cache:
            self._invalidate_session_context_cache(session_id=session.session_id)
        return mutations

    @staticmethod
    def _provider_known_models(provider: Any) -> list[str]:
        direct = getattr(provider, "available_models", None)
        if isinstance(direct, list):
            return [
                str(item) for item in direct if isinstance(item, str) and item.strip()
            ]
        if callable(direct):
            try:
                data = direct()
            except Exception:
                return []
            if isinstance(data, list):
                return [
                    str(item) for item in data if isinstance(item, str) and item.strip()
                ]
        return []

    @staticmethod
    def _session_identity(session_id: str) -> tuple[str, str]:
        parts = str(session_id or "").split(":")
        platform = parts[0] if parts and parts[0] else "unknown"
        room_id = parts[1] if len(parts) > 1 and parts[1] else ""
        return platform, room_id

    def _provider_accepts_model(self, provider: Any, model_name: str) -> bool:
        models = self._provider_known_models(provider)
        if not models:
            return True
        return model_name in models

    @staticmethod
    def _parse_shell_payload(output: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _default_mode_for_persona(self, persona: PersonaDefinition | None) -> str:
        if persona is None:
            return "default"
        profiles = persona.metadata.get("mode_profiles")
        if isinstance(profiles, dict):
            default_mode = profiles.get("default_mode")
            if isinstance(default_mode, str) and default_mode.strip():
                return default_mode.strip()
        return "default"

    def _available_modes_for_persona(self, persona: PersonaDefinition) -> set[str]:
        modes = {"default"}
        profiles = persona.metadata.get("mode_profiles")
        if not isinstance(profiles, dict):
            return modes
        available = profiles.get("available_modes")
        if not isinstance(available, list):
            return modes
        for item in available:
            if not isinstance(item, dict):
                continue
            mode_id = item.get("id")
            if isinstance(mode_id, str) and mode_id.strip():
                modes.add(mode_id.strip())
        default_mode = profiles.get("default_mode")
        if isinstance(default_mode, str) and default_mode.strip():
            modes.add(default_mode.strip())
        return modes

    @staticmethod
    def _is_visual_question(text: str) -> bool:
        """Detect if message is asking about visual content.

        Used by runtime decision path to trigger responses to image questions.
        Runtime-owned to keep visual context detection policy centralized.

        Args:
            text: Lowercase message text to analyze

        Returns:
            True if text appears to be asking about visual content
        """
        image_keywords = [
            "what is this",
            "what is that",
            "who is this",
            "who is that",
            "look at this",
            "look at that",
            "describe this",
            "describe that",
            "thoughts?",
            "opinion?",
            "can you see",
            "do you see",
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in image_keywords)

    def _inject_mode_prompt(
        self,
        persona: PersonaDefinition,
        base_prompt: str,
        mode_name: str,
    ) -> str:
        profiles = persona.metadata.get("mode_profiles")
        if not isinstance(profiles, dict):
            return base_prompt
        available = profiles.get("available_modes")
        if not isinstance(available, list):
            return base_prompt
        for item in available:
            if not isinstance(item, dict):
                continue
            mode_id = str(item.get("id") or "").strip()
            if mode_id != mode_name:
                continue
            tone = str(item.get("tone") or "").strip()
            style = str(item.get("style") or "").strip()
            details = [
                f"Active mode: {mode_id}",
                (f"Tone: {tone}" if tone else ""),
                (f"Style: {style}" if style else ""),
            ]
            suffix = "\n".join([line for line in details if line])
            prompt_override = self._load_prompt_mode_override(
                persona_id=persona.persona_id,
                mode_name=mode_id,
            )
            if prompt_override:
                suffix = (
                    f"{suffix}\n\nPrompt override ({persona.persona_id}:{mode_id}):\n"
                    f"{prompt_override}".strip()
                    if suffix
                    else prompt_override
                )
            if not suffix:
                return base_prompt
            return f"{base_prompt}\n\n{suffix}"
        return base_prompt

    def _append_session_traces(
        self,
        session: RuntimeSessionState,
        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
    ) -> None:
        for output in outputs:
            if isinstance(output, TraceOutput):
                session.trace_spans.append(output)
        if len(session.trace_spans) > 200:
            session.trace_spans = session.trace_spans[-200:]
        self._update_session_presence(session=session, outputs=outputs)

    def _update_session_presence(
        self,
        *,
        session: RuntimeSessionState,
        outputs: list[TextOutput | StructuredOutput | TraceOutput | ErrorOutput],
    ) -> None:
        now = datetime.now(timezone.utc)
        for output in outputs:
            if isinstance(output, TraceOutput):
                if output.trace_type == "provider":
                    session.last_provider_at = output.end_ts or now
                elif output.trace_type == "tool":
                    session.last_tool_at = output.end_ts or now
                continue
            if isinstance(output, ErrorOutput):
                session.last_error_at = now
                continue
            if (
                isinstance(output, TextOutput)
                and output.persona_id
                and output.persona_id != "system"
                and output.text.strip()
            ):
                session.last_response_at = now
                session.last_persona_text = output.text.strip()

    def _presence_payload(
        self,
        *,
        session: RuntimeSessionState,
        persona: PersonaDefinition | None,
        mode_name: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        has_error = self._presence_recent(session.last_error_at, now, seconds=8.0)
        tool_running = self._presence_recent(session.last_tool_at, now, seconds=4.0)
        talking = self._presence_recent(session.last_response_at, now, seconds=6.0)
        generating = (
            self._presence_recent(session.last_provider_at, now, seconds=3.0)
            and not talking
            and not tool_running
            and not has_error
        )
        state = self._derive_presence_state(
            has_error=has_error,
            yolo_enabled=session.yolo_enabled,
            tool_running=tool_running,
            generating=generating,
            talking=talking,
        )
        emotion = self._derive_presence_emotion(
            persona=persona,
            mode_name=mode_name,
            state=state,
        )
        return {
            "session_id": session.session_id,
            "persona": session.persona_id or (persona.persona_id if persona else ""),
            "mode": mode_name,
            "state": state,
            "emotion": emotion,
            "expression": emotion,
            "avatar_format": "vrm",
            "avatar_driver": "browser_vrm",
            "avatar_scene": "upper_body",
            "asset_status": "fallback_placeholder",
            "intensity": self._presence_intensity(state=state, emotion=emotion),
            "generating": generating,
            "talking": talking,
            "tool_running": tool_running,
            "yolo": session.yolo_enabled,
            "error": has_error,
            "signal_active": generating or talking or tool_running,
            "speech_text": session.last_persona_text,
            "hold_ms": 900,
            "debounce_ms": 200,
        }

    @staticmethod
    def _presence_recent(
        last_seen: datetime | None,
        now: datetime,
        *,
        seconds: float,
    ) -> bool:
        if last_seen is None:
            return False
        return (now - last_seen) <= timedelta(seconds=seconds)

    @staticmethod
    def _derive_presence_state(
        *,
        has_error: bool,
        yolo_enabled: bool,
        tool_running: bool,
        generating: bool,
        talking: bool,
    ) -> str:
        if has_error:
            return "error"
        if yolo_enabled:
            return "yolo"
        if tool_running:
            return "tool_running"
        if generating:
            return "thinking"
        if talking:
            return "talking"
        return "idle"

    def _derive_presence_emotion(
        self,
        *,
        persona: PersonaDefinition | None,
        mode_name: str,
        state: str,
    ) -> str:
        if state == "error":
            return "alarmed"
        if state == "yolo":
            return "intense"
        if state in {"tool_running", "thinking"}:
            return "focused"
        if state == "talking":
            tone = self._mode_tone(persona=persona, mode_name=mode_name)
            if tone in {"witty", "playful", "chaotic"}:
                return "amused"
            return "warm"
        return "neutral"

    @staticmethod
    def _presence_intensity(*, state: str, emotion: str) -> float:
        if state == "error":
            return 0.98
        if state == "yolo":
            return 0.92
        if state == "tool_running":
            return 0.82
        if state == "thinking":
            return 0.72
        if emotion == "amused":
            return 0.7
        if emotion == "warm":
            return 0.58
        return 0.36

    def _mode_tone(
        self,
        *,
        persona: PersonaDefinition | None,
        mode_name: str,
    ) -> str:
        if persona is None:
            return ""
        mode_profiles = persona.metadata.get("mode_profiles")
        if not isinstance(mode_profiles, dict):
            return ""
        available = mode_profiles.get("available_modes")
        if not isinstance(available, list):
            return ""
        for item in available:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "").strip() != mode_name:
                continue
            return str(item.get("tone") or "").strip().lower()
        return ""

    def _build_span_trace(
        self,
        trace_type: str,
        session_id: str,
        data: dict[str, Any],
        parent_span_id: str | None = None,
    ) -> TraceOutput:
        now = datetime.now(timezone.utc)
        return TraceOutput(
            trace_type=trace_type,
            data=dict(data),
            session_id=session_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=parent_span_id,
            start_ts=now,
            end_ts=datetime.now(timezone.utc),
        )

    @staticmethod
    def _load_prompt_mode_override(persona_id: str, mode_name: str) -> str:
        file_path = Path("prompts") / "modes" / f"{persona_id}_{mode_name}.yaml"
        if not file_path.exists():
            return ""
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""

        collecting = False
        indent = None
        content: list[str] = []
        for line in lines:
            if not collecting:
                if line.strip().startswith("system_prompt:"):
                    collecting = True
                continue
            if indent is None:
                if not line.strip():
                    continue
                indent = len(line) - len(line.lstrip(" "))
            current_indent = len(line) - len(line.lstrip(" "))
            if line.strip() and current_indent < (indent or 0):
                break
            content.append(line[indent:] if indent is not None else line)
        return "\n".join(content).strip()

    def _mcp_servers_snapshot(self) -> list[dict[str, Any]]:
        source = MCPToolSource.from_env()
        servers: list[dict[str, Any]] = []
        for server in source.servers:
            servers.append(
                {
                    "name": server.name,
                    "transport": server.transport,
                }
            )
        return servers

    @staticmethod
    def _provider_model(provider: Any) -> str:
        model = getattr(provider, "model", "")
        if isinstance(model, str) and model:
            return model
        return "unknown"

    # ------------------------------------------------------------------
    # Social state management (moved from Discord adapter for runtime ownership)
    # ------------------------------------------------------------------

    def get_social_state_snapshot(
        self,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str = "",
        room_id: str = "",
        user_id: str = "",
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get social state snapshot for a session.

        This replaces the adapter-local social state with runtime-owned state.
        Discord and other surfaces call this instead of managing state locally.

        Returns:
            Snapshot dict with override, current_mode, effective_mode, etc.
        """
        # Get session state if it exists
        session = self.session_states.get(session_id)
        if session is None:
            # Return default snapshot for new sessions
            return {
                "override": "auto",
                "current_mode": mode or "default",
                "effective_mode": mode or "default",
                "last_source": "",
                "last_confidence": 0.0,
                "mode_switches": {},
                "metadata": {"platform": platform, "room_id": room_id, "user_id": user_id},
            }

        # Extract mode from session
        current_mode = session.mode or "default"
        override = flags.get("mode_override", "auto") if flags else "auto"

        return {
            "override": override,
            "current_mode": current_mode,
            "effective_mode": current_mode,
            "last_source": getattr(session, "last_social_source", ""),
            "last_confidence": getattr(session, "last_social_confidence", 0.0),
            "mode_switches": getattr(session, "mode_switches", {}),
            "metadata": {
                "platform": platform,
                "room_id": room_id,
                "user_id": user_id,
                "persona_id": session.persona_id,
            },
        }

    def set_social_mode(
        self,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str = "",
        room_id: str = "",
        user_id: str = "",
        social_mode: str = "",
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Set social mode override for a session.

        Called by Discord /mode command and other surfaces to set mode.
        Updates the session mode and returns updated snapshot.
        """
        session = self.session_states.get(session_id)
        if session is None:
            # Create ephemeral session state for mode tracking
            return {
                "override": social_mode,
                "current_mode": social_mode,
                "effective_mode": social_mode,
                "last_source": "user_override",
                "last_confidence": 1.0,
                "mode_switches": {str(session_id): social_mode},
                "metadata": {"note": "session_not_found", "platform": platform},
            }

        old_mode = session.mode
        if social_mode and social_mode != "auto":
            session.mode = social_mode

        # Track mode switch
        if not hasattr(session, "mode_switches"):
            session.mode_switches = {}
        session.mode_switches[str(session_id)] = social_mode

        return {
            "override": social_mode,
            "current_mode": session.mode,
            "effective_mode": session.mode,
            "last_source": "user_override",
            "last_confidence": 1.0,
            "mode_switches": session.mode_switches,
            "metadata": {"old_mode": old_mode, "platform": platform},
        }

    def reset_social_state(
        self,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str = "",
        room_id: str = "",
        user_id: str = "",
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Reset social state to defaults.

        Called by Discord /mode reset and similar commands.
        """
        session = self.session_states.get(session_id)
        if session is not None:
            old_mode = session.mode
            # Reset to default mode for persona
            default_mode = self._default_mode_for_persona(
                self.personas.by_id(persona_id) if persona_id else None
            )
            session.mode = default_mode
            if hasattr(session, "mode_switches"):
                session.mode_switches = {}

            return {
                "override": "auto",
                "current_mode": session.mode,
                "effective_mode": session.mode,
                "last_source": "reset",
                "last_confidence": 0.0,
                "mode_switches": {},
                "metadata": {"old_mode": old_mode, "platform": platform},
            }

        return {
            "override": "auto",
            "current_mode": mode or "default",
            "effective_mode": mode or "default",
            "last_source": "reset",
            "last_confidence": 0.0,
            "mode_switches": {},
            "metadata": {"platform": platform, "note": "session_not_found"},
        }

    def record_social_routing_decision(
        self,
        session_id: str,
        persona_id: str,
        mode: str,
        platform: str = "",
        room_id: str = "",
        user_id: str = "",
        selected_mode: str = "",
        source: str = "",
        confidence: float = 0.0,
        metadata: dict[str, Any] | None = None,
        flags: dict[str, Any] | None = None,
    ) -> None:
        """Record a social routing decision from facilitator.

        Called by surfaces after mode selection to record the decision
        in runtime state for tracking and analytics.
        """
        session = self.session_states.get(session_id)
        if session is not None:
            session.last_social_source = source
            session.last_social_confidence = confidence
            if not hasattr(session, "social_routing_history"):
                session.social_routing_history = []
            session.social_routing_history.append({
                "mode": selected_mode,
                "source": source,
                "confidence": confidence,
                "metadata": metadata or {},
            })

    @staticmethod
    def _output_to_dict(
        item: TextOutput | StructuredOutput | TraceOutput | ErrorOutput,
    ) -> dict[str, Any]:
        if isinstance(item, TextOutput):
            return {"kind": "text", "text": item.text, "persona_id": item.persona_id}
        if isinstance(item, StructuredOutput):
            return {"kind": "structured", "type": item.kind, "data": item.data}
        if isinstance(item, TraceOutput):
            return {
                "kind": "trace",
                "trace_type": item.trace_type,
                "session_id": item.session_id,
                "span_id": item.span_id,
                "parent_span_id": item.parent_span_id,
                "start_ts": item.start_ts.isoformat(),
                "end_ts": item.end_ts.isoformat(),
                "data": item.data,
            }
        return {
            "kind": "error",
            "code": item.code,
            "message": item.message,
            "hint": item.hint,
        }

    # ------------------------------------------------------------------
    # Voice runtime contract (runtime-first voice handling)
    # ------------------------------------------------------------------

    async def handle_voice_transcription(
        self,
        session_id: str,
        transcription: str,
        user_id: str = "",
        platform: str = "",
        room_id: str = "",
        language: str = "",
        confidence: float = 0.0,
        **kwargs: Any,
    ) -> ResponseEnvelope:
        """Handle transcribed voice input by routing through runtime chat flow.

        This is the runtime-first entry point for voice transcription events.
        Adapters should call this instead of directly invoking TTS/RVC services.

        Args:
            session_id: Unique session identifier
            transcription: The transcribed text from STT
            user_id: User who spoke
            platform: Platform identifier (e.g., "discord")
            room_id: Room/channel identifier
            language: Detected language code
            confidence: STT confidence score
            **kwargs: Additional metadata

        Returns:
            ResponseEnvelope with text output and optional VoiceOutputIntent
        """
        from core.schemas import Event, EventKind

        # Create a standard event for the chat flow
        event = Event(
            type="voice_transcription",
            kind=EventKind.VOICE_TRANSCRIPTION.value,
            text=transcription,
            user_id=user_id,
            room_id=room_id,
            platform=platform,
            session_id=session_id,
            metadata={
                "language": language,
                "confidence": confidence,
                "source": "voice",
                **kwargs,
            },
        )

        # Run through standard chat flow
        envelope = await self.handle_event_envelope(event)

        # Check if response should include voice output intent
        # This allows the runtime to signal TTS intent without directly controlling audio
        voice_intent = self._extract_voice_intent_from_envelope(envelope)
        if voice_intent:
            # Add voice intent as structured output for adapter to consume
            envelope.outputs.append(
                StructuredOutput(
                    kind="voice_output_intent",
                    data={
                        "text": voice_intent.text,
                        "tts_voice": voice_intent.tts_voice,
                        "tts_speed": voice_intent.tts_speed,
                        "rvc_enabled": voice_intent.rvc_enabled,
                        "rvc_model": voice_intent.rvc_model,
                        "rvc_pitch_shift": voice_intent.rvc_pitch_shift,
                        "rvc_index_rate": voice_intent.rvc_index_rate,
                        "rvc_protect": voice_intent.rvc_protect,
                        "priority": voice_intent.priority,
                    },
                )
            )

        return envelope

    def _extract_voice_intent_from_envelope(
        self, envelope: ResponseEnvelope
    ) -> "VoiceOutputIntent | None":
        """Extract voice output intent from envelope if present.

        Currently derives from session state and response content.
        Future: runtime can decide voice characteristics based on persona/mode.
        """
        session = self.session_states.get(envelope.session_id)
        if not session:
            return None

        # Get the text output from envelope
        text = ""
        for output in envelope.outputs:
            if isinstance(output, TextOutput) and output.text:
                text = output.text
                break

        if not text:
            return None

        # Create voice intent with runtime-determined settings
        # Future: these could come from persona config, mode, or tool results
        return VoiceOutputIntent(
            text=text,
            tts_voice=session.flags.get("tts_voice", ""),
            tts_speed=float(session.flags.get("tts_speed", 1.0)),
            rvc_enabled=bool(session.flags.get("rvc_enabled", False)),
            rvc_model=str(session.flags.get("rvc_model", "")),
            rvc_pitch_shift=int(session.flags.get("rvc_pitch_shift", 0)),
            rvc_index_rate=float(session.flags.get("rvc_index_rate", 0.75)),
            rvc_protect=float(session.flags.get("rvc_protect", 0.33)),
            priority=False,
        )

    def create_voice_output_intent(
        self,
        session_id: str,
        text: str,
        tts_voice: str = "",
        tts_speed: float = 0.0,
        rvc_enabled: bool = False,
        rvc_model: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a voice output intent dict for adapter consumption.

        This is a factory method for creating voice output intents
        that adapters can use to configure TTS/RVC execution.

        Args:
            session_id: Session identifier for context
            text: Text to speak
            tts_voice: TTS voice identifier
            tts_speed: TTS speed multiplier (0.0 means use default)
            rvc_enabled: Whether to apply RVC conversion
            rvc_model: RVC model name
            **kwargs: Additional RVC parameters (pitch_shift, index_rate, protect)

        Returns:
            Dict with voice output configuration
        """
        session = self.session_states.get(session_id)

        # Get session-stored voice settings if available
        if session:
            tts_voice = tts_voice or session.flags.get("tts_voice", "")
            # Only use session speed if no explicit speed provided (> 0)
            session_speed = float(session.flags.get("tts_speed", 0.0))
            tts_speed = tts_speed if tts_speed > 0 else (session_speed if session_speed > 0 else 1.0)
            # Use explicit rvc_enabled or session setting
            if not rvc_enabled:
                rvc_enabled = bool(session.flags.get("rvc_enabled", False))
            rvc_model = rvc_model or str(session.flags.get("rvc_model", ""))
        else:
            # Default speed if no session
            tts_speed = tts_speed if tts_speed > 0 else 1.0

        return {
            "text": text,
            "tts_voice": tts_voice,
            "tts_speed": tts_speed,
            "rvc_enabled": rvc_enabled,
            "rvc_model": rvc_model,
            "rvc_pitch_shift": kwargs.get("rvc_pitch_shift", 0),
            "rvc_index_rate": kwargs.get("rvc_index_rate", 0.75),
            "rvc_protect": kwargs.get("rvc_protect", 0.33),
            "priority": kwargs.get("priority", False),
        }
