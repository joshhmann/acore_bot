"""Web adapter for Gestalt Framework using FastAPI.

This module provides the main WebInputAdapter class that integrates
FastAPI, WebSocket support, and HTTP endpoints for the Gestalt runtime.

The adapter follows the AdapterLifecycleContract pattern with four phases:
1. parse: Extract PlatformFacts from web request payload
2. to_runtime_event: Build runtime Event using shared helper
3. from_runtime_response: Extract RuntimeDecision from Response
4. render: Return JSON response via web transport

The adapter delegates to separate modules:
- auth.py: Authentication handling
- routes.py: HTTP API routes
- websocket.py: WebSocket handlers
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Callable

from gestalt.runtime_bootstrap import create_runtime as _create_runtime
from core.interfaces import (
    AdapterConfig,
    AdapterLifecycleContract,
    InputAdapter,
    AcoreEvent,
    PlatformFacts,
    RuntimeDecision,
)
from core.schemas import Response

if TYPE_CHECKING:
    from core.runtime import GestaltRuntime

# FastAPI imports with fallback
try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse, JSONResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = object  # type: ignore
    CORSMiddleware = object  # type: ignore
    StaticFiles = object  # type: ignore
    FileResponse = object  # type: ignore
    JSONResponse = object  # type: ignore

logger = logging.getLogger(__name__)


def create_runtime(*, legacy_llm: Any | None = None) -> "GestaltRuntime":
    """Build runtime for web adapter; patched in tests for deterministic fakes."""
    return _create_runtime(legacy_llm=legacy_llm)


class WebAdapter(AdapterLifecycleContract[dict, str]):
    """Web platform adapter implementing the AdapterLifecycleContract.

    This adapter follows the formalized four-phase lifecycle:
    - parse: Extracts PlatformFacts from HTTP request payload (dict)
    - to_runtime_event: Uses shared build_runtime_event_from_facts helper
    - from_runtime_response: Creates RuntimeDecision from runtime Response
    - render: Performs transport-level rendering hook

    Platform capabilities:
    - platform_name: "web"
    - supports_embeds: True (for rich JSON responses)
    - supports_threads: False
    - supports_reactions: False

    Example:
        adapter = WebAdapter()
        facts = adapter.parse({
            "text": "Hello",
            "user_id": "user123",
            "room_id": "room456"
        })
        event = adapter.to_runtime_event(facts)
        # ... process with runtime ...
        decision = adapter.from_runtime_response(response, facts)
        await adapter.render("response_channel", decision, response)
    """

    def __init__(self) -> None:
        """Initialize the web adapter with platform configuration."""
        super().__init__(
            AdapterConfig(
                platform_name="web",
                supports_embeds=True,
                supports_threads=False,
                supports_reactions=False,
                max_message_length=0,  # No limit for web
            )
        )

    def parse(self, request_payload: dict) -> PlatformFacts:
        """Phase 1: Extract PlatformFacts from web request payload.

        Parses HTTP/websocket request data into normalized facts for runtime
        processing. Web requests are expected to contain standard message
        fields in JSON format.

        Args:
            request_payload: Dictionary containing web request data with keys:
                - text: Message content (required)
                - user_id: Platform user identifier (required)
                - room_id: Room/channel identifier (required)
                - message_id: Optional message identifier
                - is_direct_mention: Whether bot was mentioned
                - is_reply_to_bot: Whether this is a reply to bot
                - author_is_bot: Whether author is a bot account
                - has_visual_context: Whether message has attachments
                - platform_flags: Additional platform-specific flags
                - raw_metadata: Debug/metadata information

        Returns:
            PlatformFacts with extracted and normalized information.

        Example:
            facts = adapter.parse({
                "text": "Hello bot",
                "user_id": "user_123",
                "room_id": "room_456",
                "message_id": "msg_789",
            })
        """
        text = str(request_payload.get("text", ""))
        user_id = str(request_payload.get("user_id", "web_user"))
        room_id = str(request_payload.get("room_id", "web_channel"))
        message_id = str(request_payload.get("message_id", ""))

        # Extract boolean flags with defaults
        is_direct_mention = bool(request_payload.get("is_direct_mention", False))
        is_reply_to_bot = bool(request_payload.get("is_reply_to_bot", False))
        is_persona_message = bool(request_payload.get("is_persona_message", False))
        has_visual_context = bool(request_payload.get("has_visual_context", False))
        author_is_bot = bool(request_payload.get("author_is_bot", False))

        # Extract optional flag dictionaries
        platform_flags: dict[str, Any] = {}
        if isinstance(request_payload.get("platform_flags"), dict):
            platform_flags = dict(request_payload["platform_flags"])

        raw_metadata: dict[str, Any] = {}
        if isinstance(request_payload.get("raw_metadata"), dict):
            raw_metadata = dict(request_payload["raw_metadata"])

        # Add web-specific context to platform_flags
        platform_flags.setdefault("platform", "web")
        if "client_id" in request_payload:
            platform_flags["client_id"] = request_payload["client_id"]
        if "session_id" in request_payload:
            platform_flags["session_id"] = request_payload["session_id"]

        return PlatformFacts(
            text=text,
            user_id=user_id,
            room_id=room_id,
            message_id=message_id,
            is_direct_mention=is_direct_mention,
            is_reply_to_bot=is_reply_to_bot,
            is_persona_message=is_persona_message,
            has_visual_context=has_visual_context,
            author_is_bot=author_is_bot,
            platform_flags=platform_flags,
            raw_metadata=raw_metadata,
        )

    def build_response_payload(
        self,
        decision: RuntimeDecision,
        response: Response,
    ) -> dict[str, Any]:
        """Build a JSON-serializable payload for web transport.

        This is a web-specific helper layered on top of the shared lifecycle
        contract. It does not replace the shared `render()` transport phase.
        """
        from datetime import datetime, timezone

        return {
            "response": response.text if decision.should_respond else "",
            "persona_id": response.persona_id,
            "persona_name": response.persona_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                **response.metadata,
                "should_respond": decision.should_respond,
                "decision_reason": decision.reason,
                "suggested_style": decision.suggested_style,
            },
            "decision": {
                "should_respond": decision.should_respond,
                "reason": decision.reason,
                "suggested_style": decision.suggested_style,
                "persona_id": decision.persona_id,
                "session_id": decision.session_id,
            },
        }

    async def render(
        self,
        response_channel: str,
        decision: RuntimeDecision,
        response: Response,
    ) -> None:
        """Phase 4: Transport/render hook for the shared adapter lifecycle.

        For HTTP routes the transport boundary is the route handler itself, so
        this hook intentionally performs no I/O. Use `build_response_payload()`
        to construct web-specific response envelopes.
        """
        return None


class WebInputAdapter(InputAdapter):
    """Input adapter that exposes HTTP API for receiving messages.

    Provides:
    - REST API endpoints for chat and persona management
    - WebSocket support for real-time streaming
    - API key authentication
    - Integration with GestaltRuntime

    This adapter uses WebAdapter internally for the lifecycle contract
    while maintaining backward compatibility with existing web routes.

    Usage:
        adapter = WebInputAdapter(host="0.0.0.0", port=8000)
        await adapter.start()
        # ... run until shutdown
        await adapter.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        runtime: "GestaltRuntime" | None = None,
    ):
        """Initialize the web input adapter.

        Args:
            host: Host to bind the server to (default: 0.0.0.0).
            port: Port to listen on (default: 8000).
            runtime: Optional GestaltRuntime instance. If not provided,
                    one will be built using runtime_factory.
        """
        super().__init__()
        self.host = host
        self.port = port
        self._event_callback: Callable[[AcoreEvent], None] | None = None
        self._app: FastAPI | None = None
        self._server: Any = None
        self._running = False
        self._stored_messages: list[dict[str, Any]] = []
        self._runtime = runtime or create_runtime()

        # Initialize the SDK-contract web adapter for lifecycle methods
        self._web_adapter = WebAdapter()

        # Load API token from environment
        self._api_token = str(
            os.environ.get("GESTALT_API_TOKEN")
            or os.environ.get("ACORE_WEB_API_TOKEN")
            or ""
        ).strip()

        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not installed. Web adapter disabled.")
            return

        self._setup_app()

    def _setup_app(self) -> None:
        """Setup FastAPI application."""
        if not FASTAPI_AVAILABLE:
            return

        # Import modules here to avoid issues if FastAPI not installed
        from .auth import WebAuth
        from .routes import create_router
        from .websocket import WebSocketManager

        # Initialize auth
        self._auth = WebAuth(self._api_token)
        self._ws_manager = WebSocketManager(
            runtime=self._runtime,
            api_token=self._api_token,
            event_callback=self._event_callback,
        )

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan handler."""
            logger.info("Web adapter starting up")
            yield
            logger.info("Web adapter shutting down")

        self._app = FastAPI(
            title="Gestalt Framework API",
            description="HTTP API for interacting with AI personas",
            version="1.0.0",
            lifespan=lifespan,
        )

        # Add CORS middleware
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount static files
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            self._app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # Create and include router
        router = create_router(
            runtime=self._runtime,
            auth=self._auth,
            stored_messages=self._stored_messages,
            web_adapter=self._web_adapter,
        )
        self._app.include_router(router)

        # Setup WebSocket routes
        self._setup_websocket_routes()

        # Add root route
        @self._app.get("/")
        async def root():
            """Serve the chat UI or API info."""
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {
                "message": "Gestalt Framework API",
                "docs": "/docs",
                "version": "1.0.0",
            }

    def _setup_websocket_routes(self) -> None:
        """Setup WebSocket endpoint routes."""
        if self._app is None:
            return

        # Runtime protocol WebSocket
        @self._app.websocket("/api/runtime/ws")
        async def runtime_websocket(websocket: WebSocket):
            """Runtime protocol WebSocket endpoint."""
            await self._ws_manager.handle_runtime_websocket(websocket)

        # Simple chat WebSocket
        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Simple chat WebSocket endpoint."""
            await self._ws_manager.handle_simple_websocket(websocket)

    async def start(self) -> None:
        """Start the web server.

        Raises:
            ImportError: If FastAPI/uvicorn is not installed.
        """
        if not FASTAPI_AVAILABLE:
            logger.error("Cannot start web adapter: FastAPI not installed")
            return

        if self._running:
            logger.warning("WebInputAdapter is already running")
            return

        self._running = True
        logger.info(f"Starting WebInputAdapter on {self.host}:{self.port}")

        import uvicorn

        config = uvicorn.Config(
            self._app, host=self.host, port=self.port, log_level="info"
        )
        self._server = uvicorn.Server(config)

        # Start server in background task
        asyncio.create_task(self._server.serve())

    async def stop(self) -> None:
        """Stop the web server gracefully."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping WebInputAdapter")

        if self._server:
            self._server.should_exit = True
            await asyncio.sleep(0.5)

    def on_event(self, callback: Callable[[AcoreEvent], None]) -> None:
        """Register a callback to handle incoming events.

        Args:
            callback: Function called with each AcoreEvent received.
        """
        self._event_callback = callback
        # Update websocket manager with callback
        if hasattr(self, "_ws_manager"):
            self._ws_manager.event_callback = callback
        logger.debug("Event callback registered for WebInputAdapter")

    def get_stored_messages(self) -> list[dict[str, Any]]:
        """Get list of stored messages for processing."""
        return self._stored_messages.copy()

    def clear_stored_messages(self) -> None:
        """Clear the stored messages list."""
        self._stored_messages.clear()

    def is_running(self) -> bool:
        """Check if the web adapter is running."""
        return self._running

    @property
    def app(self) -> FastAPI | None:
        """Get the FastAPI application instance."""
        return self._app

    @property
    def runtime(self) -> "GestaltRuntime":
        """Get the GestaltRuntime instance."""
        return self._runtime

    @property
    def web_adapter(self) -> WebAdapter:
        """Get the WebAdapter instance for SDK contract methods.

        Returns:
            WebAdapter implementing AdapterLifecycleContract.
        """
        return self._web_adapter


class WebOutputAdapter:
    """Output adapter for web responses.

    This is a compatibility wrapper around the existing output adapter.
    For new code, use the one from .output module directly.
    """

    def __init__(self, event_bus: Any = None):
        """Initialize output adapter."""
        from .output import WebOutputAdapter as _WebOutputAdapter

        self._adapter = _WebOutputAdapter(event_bus=event_bus)

    async def send(self, channel_id: str, text: str, **options: Any) -> None:
        """Send a text message."""
        await self._adapter.send(channel_id, text, **options)

    async def send_embed(self, channel_id: str, embed: dict) -> None:
        """Send rich embedded content."""
        await self._adapter.send_embed(channel_id, embed)


__all__ = [
    "WebAdapter",
    "WebInputAdapter",
    "WebOutputAdapter",
]
