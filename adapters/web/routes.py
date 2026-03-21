"""HTTP routes for Web Adapter.

Provides REST API endpoints for:
- Health checks
- Chat interactions
- Persona management
- Runtime introspection

Routes use the WebAdapter lifecycle contract for SDK-compliant
request processing and response rendering.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from core.schemas import EventKind

from .api_schema import (
    ChatAsyncRequest,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    PersonaInfo,
    RuntimeContextRequest,
    RuntimeEventRequest,
    RuntimeListSessionsRequest,
    RuntimeSocialModeRequest,
    RuntimeTraceRequest,
)
from .auth import (
    WebAuth,
    extract_request_client_scope,
    extract_request_user_id,
    get_auth,
    resolve_request_actor_id,
)

if TYPE_CHECKING:
    from core.runtime import GestaltRuntime
    from .adapter import WebAdapter

# FastAPI imports with fallback
try:
    from fastapi import APIRouter, HTTPException, Request, BackgroundTasks

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object  # type: ignore
    HTTPException = Exception  # type: ignore
    Request = object  # type: ignore
    BackgroundTasks = object  # type: ignore

logger = logging.getLogger(__name__)


def _runtime_context_payload(
    request: RuntimeContextRequest,
    *,
    client_scope: str = "",
    user_id: str = "",
    auth_enabled: bool = False,
    claimed_user_id: str = "",
) -> dict[str, Any]:
    """Convert context request to runtime payload dict."""
    flags = dict(request.flags)
    if client_scope and not str(flags.get("user_scope") or "").strip():
        flags["user_scope"] = client_scope
    request_claim = str(request.user_id or "").strip()
    effective_claimed_user_id = str(claimed_user_id or request_claim).strip()
    resolved_user_id = user_id or effective_claimed_user_id
    if (
        auth_enabled
        and effective_claimed_user_id
        and effective_claimed_user_id != resolved_user_id
    ):
        flags.setdefault("claimed_user_id", effective_claimed_user_id)
    if resolved_user_id and not str(flags.get("user_id") or "").strip():
        flags["user_id"] = resolved_user_id
    return {
        "session_id": request.session_id,
        "persona_id": request.persona_id,
        "mode": request.mode,
        "platform": request.platform,
        "room_id": request.room_id,
        "flags": flags,
    }


def _serialize_output(output: Any) -> dict[str, Any]:
    """Serialize output object to dict."""
    data = asdict(output) if hasattr(output, "__dataclass_fields__") else {}
    data["type"] = (
        output.__class__.__name__ if hasattr(output, "__class__") else "unknown"
    )
    return data


def _serialize_mutation(mutation: Any) -> dict[str, Any]:
    """Serialize mutation object to dict."""
    if hasattr(mutation, "__dataclass_fields__"):
        return asdict(mutation)
    return {"path": str(mutation), "old": None, "new": None}


def create_router(
    runtime: "GestaltRuntime",
    auth: WebAuth | None = None,
    stored_messages: list[dict[str, Any]] | None = None,
    web_adapter: "WebAdapter" | None = None,
) -> APIRouter:
    """Create FastAPI router with all web adapter routes.

    Args:
        runtime: The GestaltRuntime instance for handling events.
        auth: Optional WebAuth instance for authentication.
        stored_messages: Optional list for storing async message data.
        web_adapter: Optional WebAdapter for SDK lifecycle contract.

    Returns:
        Configured APIRouter instance.
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is required for web routes")

    from .adapter import WebAdapter

    router = APIRouter()
    auth = auth or get_auth()
    messages_store = stored_messages if stored_messages is not None else []
    _web_adapter = web_adapter or WebAdapter()

    def _require_auth(request: Request) -> None:
        """Helper to require authentication."""
        auth.require_auth(request)

    def _default_persona_id() -> str:
        return str(getattr(runtime.router, "default_persona_id", "default") or "default")

    @router.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint.

        Returns:
            HealthResponse with service status and runtime info.
        """
        personas = getattr(runtime, "personas", {})
        return HealthResponse(
            status="healthy",
            personas_loaded=len(personas) if personas else 0,
            uptime_seconds=0.0,
            version="1.0.0",
        )

    @router.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """Synchronous chat endpoint using SDK lifecycle contract.

        Uses the WebAdapter's four-phase lifecycle:
        1. parse: Extract PlatformFacts from request
        2. to_runtime_event: Build runtime Event
        3. from_runtime_response: Extract decision from response
        4. render: Return JSON response

        Args:
            request: ChatRequest with message and persona configuration.

        Returns:
            ChatResponse with persona response text.
        """
        try:
            # Phase 1: Parse request into PlatformFacts
            facts = _web_adapter.parse(
                {
                    "text": request.message,
                    "user_id": request.user_id or "web_user",
                    "room_id": request.channel_id or "web_channel",
                }
            )

            # Phase 2: Build runtime Event from facts
            event = _web_adapter.to_runtime_event(
                facts,
                kind=EventKind.CHAT.value,
                persona_id=request.persona_id or _default_persona_id(),
            )

            # Process with runtime
            runtime_response = await runtime.handle_event(event)

            # Phase 3: Extract decision from runtime response
            decision = _web_adapter.from_runtime_response(runtime_response, facts)

            # Phase 4: Transport hook + web-specific payload shaping
            await _web_adapter.render(
                request.channel_id or "web_channel", decision, runtime_response
            )
            rendered = _web_adapter.build_response_payload(decision, runtime_response)

            return ChatResponse(
                response=rendered["response"],
                persona_id=rendered["persona_id"],
                persona_name=rendered["persona_name"],
                timestamp=datetime.now(timezone.utc),
                metadata=rendered["metadata"],
            )
        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/chat/async")
    async def chat_async(
        request: ChatAsyncRequest, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Asynchronous chat endpoint - accepts message and returns immediately.

        Uses SDK lifecycle contract for request normalization.

        Args:
            request: ChatAsyncRequest with message and optional webhook URL.
            background_tasks: FastAPI background tasks handler.

        Returns:
            Dict with status and message_id.
        """
        # Use WebAdapter.parse to normalize request data
        facts = _web_adapter.parse(
            {
                "text": request.message,
                "user_id": request.user_id or "web_user",
                "room_id": request.channel_id or "web_channel",
            }
        )

        message_data: dict[str, Any] = {
            "message": facts.text,
            "persona_id": request.persona_id,
            "user_id": facts.user_id,
            "channel_id": facts.room_id,
            "context": request.context,
            "webhook_url": request.webhook_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "platform_flags": facts.platform_flags,
        }
        messages_store.append(message_data)
        message_id = len(messages_store) - 1

        return {
            "status": "accepted",
            "message_id": message_id,
            "webhook_url": request.webhook_url,
        }

    @router.get("/personas")
    async def list_personas() -> dict[str, list[PersonaInfo]]:
        """List available personas.

        Returns:
            Dict with list of PersonaInfo objects.
        """
        personas_catalog = getattr(runtime, "personas", None)
        persona_list: list[PersonaInfo] = []

        if personas_catalog is None:
            return {"personas": persona_list}

        # Handle PersonaCatalog object
        if hasattr(personas_catalog, "all"):
            # It's a PersonaCatalog
            for persona in personas_catalog.all():
                persona_list.append(
                    PersonaInfo(
                        id=persona.persona_id,
                        display_name=persona.display_name,
                        description=persona.description,
                        avatar_url=persona.metadata.get("avatar_url") if persona.metadata else None,
                    )
                )
        elif isinstance(personas_catalog, dict):
            # Legacy dict format
            for persona_id, persona in personas_catalog.items():
                if isinstance(persona, dict):
                    persona_list.append(
                        PersonaInfo(
                            id=persona_id,
                            display_name=persona.get("display_name", persona_id),
                            description=persona.get("description"),
                            avatar_url=persona.get("avatar_url"),
                        )
                    )
                else:
                    # Handle Persona dataclass objects
                    persona_list.append(
                        PersonaInfo(
                            id=persona_id,
                            display_name=getattr(persona, "display_name", persona_id),
                            description=getattr(persona, "description", None),
                            avatar_url=getattr(persona, "avatar_url", None),
                        )
                    )

        return {"personas": persona_list}

    @router.get("/personas/{persona_id}")
    async def get_persona(persona_id: str) -> PersonaInfo:
        """Get specific persona details.

        Args:
            persona_id: The persona identifier.

        Returns:
            PersonaInfo for the requested persona.

        Raises:
            HTTPException: If persona not found (404).
        """
        personas_catalog = getattr(runtime, "personas", None)

        if personas_catalog is None:
            raise HTTPException(
                status_code=404, detail=f"Persona '{persona_id}' not found"
            )

        # Handle PersonaCatalog object
        if hasattr(personas_catalog, "by_id"):
            # It's a PersonaCatalog
            persona = personas_catalog.by_id(persona_id)
            if persona is None:
                raise HTTPException(
                    status_code=404, detail=f"Persona '{persona_id}' not found"
                )
            return PersonaInfo(
                id=persona.persona_id,
                display_name=persona.display_name,
                description=persona.description,
                avatar_url=persona.metadata.get("avatar_url") if persona.metadata else None,
            )
        elif isinstance(personas_catalog, dict):
            # Legacy dict format
            if persona_id not in personas_catalog:
                raise HTTPException(
                    status_code=404, detail=f"Persona '{persona_id}' not found"
                )

            persona = personas_catalog[persona_id]
            if isinstance(persona, dict):
                return PersonaInfo(
                    id=persona_id,
                    display_name=persona.get("display_name", persona_id),
                    description=persona.get("description"),
                    avatar_url=persona.get("avatar_url"),
                )
            else:
                return PersonaInfo(
                    id=persona_id,
                    display_name=getattr(persona, "display_name", persona_id),
                    description=getattr(persona, "description", None),
                    avatar_url=getattr(persona, "avatar_url", None),
                )
        else:
            raise HTTPException(
                status_code=404, detail=f"Persona '{persona_id}' not found"
            )

    @router.post("/personas/{persona_id}/activate")
    async def activate_persona(persona_id: str, request: Request) -> dict[str, str]:
        """Activate a specific persona for the session.

        Args:
            persona_id: The persona to activate.
            request: FastAPI request for auth.

        Returns:
            Dict with status and activated persona_id.
        """
        _require_auth(request)

        personas = getattr(runtime, "personas", {})
        if persona_id not in personas:
            raise HTTPException(
                status_code=404, detail=f"Persona '{persona_id}' not found"
            )

        return {"status": "activated", "persona_id": persona_id}

    @router.get("/messages")
    async def get_stored_messages(request: Request) -> dict[str, Any]:
        """Get stored messages for processing (for internal/debug use).

        Args:
            request: FastAPI request for auth.

        Returns:
            Dict with count and list of stored messages.
        """
        _require_auth(request)

        return {
            "count": len(messages_store),
            "messages": messages_store,
        }

    # Runtime API routes (require authentication)

    @router.get("/api/runtime/health")
    async def runtime_health(request: Request) -> dict[str, Any]:
        """Runtime health status."""
        _require_auth(request)
        return {
            "running": True,
            "command": "web runtime",
            "auth_required": auth.is_enabled,
        }

    @router.get("/api/runtime/commands")
    async def runtime_commands(request: Request) -> dict[str, Any]:
        """List available runtime commands."""
        _require_auth(request)
        return {"commands": runtime.list_commands()}

    @router.post("/api/runtime/status")
    async def runtime_status(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime status snapshot."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.get_status_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/session")
    async def runtime_session(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get or bootstrap a runtime session summary."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "session": runtime.get_session_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/sessions")
    async def runtime_sessions(
        request: RuntimeListSessionsRequest, http_request: Request
    ) -> dict[str, Any]:
        """List recent runtime sessions."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        return {
            "sessions": runtime.list_sessions_snapshot(
                limit=max(1, int(request.limit)),
                platform=str(request.platform or ""),
                room_id=str(request.room_id or ""),
                user_scope=str(request.user_scope or client_scope or ""),
            )
        }

    @router.post("/api/runtime/tools")
    async def runtime_tools(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime tools snapshot."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "tools": runtime.get_tools_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/context")
    async def runtime_context_cache(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime context-cache snapshot."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.get_context_cache_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/context/reset")
    async def runtime_context_cache_reset(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Reset runtime context-cache entries for a session."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.reset_context_cache(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/trace")
    async def runtime_trace(
        request: RuntimeTraceRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime trace snapshot."""
        _require_auth(http_request)
        return {
            "trace": runtime.get_trace_snapshot(
                session_id=request.session_id, limit=max(1, int(request.limit))
            )
        }

    @router.post("/api/runtime/presence")
    async def runtime_presence(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime presence snapshot."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.get_presence_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/social")
    async def runtime_social(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime social-state snapshot."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.get_social_state_snapshot(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/social/mode")
    async def runtime_social_mode(
        request: RuntimeSocialModeRequest, http_request: Request
    ) -> dict[str, Any]:
        """Set runtime social-mode override."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        payload = _runtime_context_payload(
            request,
            client_scope=client_scope,
            user_id=user_id,
            auth_enabled=auth.is_enabled,
            claimed_user_id=claimed_user_id,
        )
        return {
            "snapshot": runtime.set_social_mode(
                **payload,
                social_mode=request.social_mode,
            )
        }

    @router.post("/api/runtime/social/reset")
    async def runtime_social_reset(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Reset runtime social state for the session."""
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        user_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        return {
            "snapshot": runtime.reset_social_state(
                **_runtime_context_payload(
                    request,
                    client_scope=client_scope,
                    user_id=user_id,
                    auth_enabled=auth.is_enabled,
                    claimed_user_id=claimed_user_id,
                )
            )
        }

    @router.post("/api/runtime/providers")
    async def runtime_providers(
        request: RuntimeContextRequest, http_request: Request
    ) -> dict[str, Any]:
        """Get runtime providers snapshot."""
        _require_auth(http_request)
        return {
            "providers": runtime.get_providers_snapshot(session_id=request.session_id)
        }

    @router.post("/api/runtime/event")
    async def runtime_event(
        request: RuntimeEventRequest, http_request: Request
    ) -> dict[str, Any]:
        """Send event to runtime and return envelope using SDK lifecycle contract.

        Uses the WebAdapter's four-phase lifecycle for event processing.
        """
        _require_auth(http_request)
        client_scope = extract_request_client_scope(http_request)
        claimed_user_id = extract_request_user_id(http_request)
        actor_id = resolve_request_actor_id(
            http_request,
            auth=auth,
            client_scope=client_scope,
            platform=request.platform,
        )
        context = _runtime_context_payload(
            request,
            client_scope=client_scope,
            user_id=actor_id,
            auth_enabled=auth.is_enabled,
            claimed_user_id=claimed_user_id,
        )

        kind = str(request.kind or EventKind.CHAT.value).strip().lower()

        # Phase 1: Parse request into PlatformFacts
        facts = _web_adapter.parse(
            {
                "text": request.text,
                "user_id": actor_id,
                "room_id": request.room_id,
                "message_id": str(getattr(request, "message_id", "") or ""),
                "platform_flags": {"client_scope": client_scope},
            }
        )

        # Phase 2: Build runtime Event from facts
        event = _web_adapter.to_runtime_event(
            facts,
            session_id=request.session_id,
            persona_id=context["persona_id"] or _default_persona_id(),
            mode=context["mode"],
            kind=kind,
            extra_flags=dict(context["flags"]),
        )

        try:
            envelope = await runtime.handle_event_envelope(event)
            return {
                "event_id": envelope.event_id,
                "session_id": envelope.session_id,
                "outputs": [_serialize_output(out) for out in envelope.outputs],
                "mutations": [_serialize_mutation(m) for m in envelope.mutations],
            }
        except Exception as e:
            logger.error(f"Error handling runtime event: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
