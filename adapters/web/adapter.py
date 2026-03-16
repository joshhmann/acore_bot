"""Web adapter for Gestalt Framework using FastAPI.

This module provides the main WebInputAdapter class that integrates
FastAPI, WebSocket support, and HTTP endpoints for the Gestalt runtime.

The adapter delegates to separate modules:
- auth.py: Authentication handling
- routes.py: HTTP API routes
- websocket.py: WebSocket handlers
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from gestalt.runtime_bootstrap import create_runtime as _create_runtime
from core.interfaces import InputAdapter, AcoreEvent

if TYPE_CHECKING:
    from core.runtime import GestaltRuntime

# FastAPI imports with fallback
try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, WebSocket
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = object  # type: ignore
    CORSMiddleware = object  # type: ignore
    StaticFiles = object  # type: ignore
    FileResponse = object  # type: ignore

logger = logging.getLogger(__name__)


def create_runtime(*, legacy_llm: Any | None = None) -> "GestaltRuntime":
    """Build runtime for web adapter; patched in tests for deterministic fakes."""
    return _create_runtime(legacy_llm=legacy_llm)


class WebInputAdapter(InputAdapter):
    """Input adapter that exposes HTTP API for receiving messages.

    Provides:
    - REST API endpoints for chat and persona management
    - WebSocket support for real-time streaming
    - API key authentication
    - Integration with GestaltRuntime

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
        runtime: Optional["GestaltRuntime"] = None,
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
        self._event_callback: Optional[Callable[[AcoreEvent], None]] = None
        self._app: Optional[FastAPI] = None
        self._server: Any = None
        self._running = False
        self._stored_messages: List[Dict[str, Any]] = []
        self._runtime = runtime or create_runtime()

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
            self._app, host=self.host, port=self._port, log_level="info"
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

    def get_stored_messages(self) -> List[Dict[str, Any]]:
        """Get list of stored messages for processing."""
        return self._stored_messages.copy()

    def clear_stored_messages(self) -> None:
        """Clear the stored messages list."""
        self._stored_messages.clear()

    def is_running(self) -> bool:
        """Check if the web adapter is running."""
        return self._running

    @property
    def app(self) -> Optional[FastAPI]:
        """Get the FastAPI application instance."""
        return self._app

    @property
    def runtime(self) -> "GestaltRuntime":
        """Get the GestaltRuntime instance."""
        return self._runtime


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
    "WebInputAdapter",
    "WebOutputAdapter",
]
