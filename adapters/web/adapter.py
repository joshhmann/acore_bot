"""Web adapter for Gestalt Framework using FastAPI."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.interfaces import InputAdapter, AcoreEvent
from core.types import AcoreMessage
from .api_schema import ChatRequest, ChatAsyncRequest, ChatResponse, HealthResponse

try:
    from fastapi import (
        FastAPI,
        HTTPException,
        BackgroundTasks,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    from contextlib import asynccontextmanager
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    HTTPException = None
    BackgroundTasks = None
    CORSMiddleware = None
    uvicorn = None
    WebSocket = None
    WebSocketDisconnect = None

logger = logging.getLogger(__name__)


class WebInputAdapter(InputAdapter):
    """Input adapter that exposes HTTP API for receiving messages."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        super().__init__()
        self.host = host
        self.port = port
        self._event_callback: Optional[Callable[[AcoreEvent], None]] = None
        self._app: Optional[Any] = None
        self._server: Optional[Any] = None
        self._running = False
        self._stored_messages: List[Dict[str, Any]] = []

        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not installed. Web adapter disabled.")
            return

        self._setup_app()

    def _setup_app(self):
        """Setup FastAPI application."""

        @asynccontextmanager
        async def lifespan(app):
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
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse
        import os

        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            self._app.mount("/static", StaticFiles(directory=static_dir), name="static")

        # Setup routes
        self._setup_routes()
        self._setup_websocket()

        # Add root route to serve index.html
        @self._app.get("/")
        async def root():
            """Serve the chat UI."""
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return {"message": "Gestalt Framework API", "docs": "/docs"}

    def _setup_websocket(self):
        """Setup WebSocket endpoint for real-time chat."""

        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for streaming chat."""
            await websocket.accept()
            client_id = f"ws_{id(websocket)}"
            logger.info(f"WebSocket client connected: {client_id}")

            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_json()

                    message_text = data.get("message", "")
                    persona_id = data.get("persona_id", "dagoth_ur")
                    user_id = data.get("user_id", client_id)

                    if not message_text:
                        await websocket.send_json(
                            {"type": "error", "message": "No message provided"}
                        )
                        continue

                    # Create AcoreMessage
                    message = AcoreMessage(
                        text=message_text,
                        author_id=user_id,
                        channel_id=client_id,
                        timestamp=datetime.utcnow(),
                    )

                    # Create event
                    event = AcoreEvent(
                        type="message",
                        payload={
                            "message": message,
                            "persona_id": persona_id,
                            "websocket": websocket,
                        },
                        source_adapter="web",
                    )

                    # Send to event callback
                    if self._event_callback:
                        result = self._event_callback(event)
                        if asyncio.iscoroutine(result):
                            asyncio.create_task(result)

                    # Send acknowledgment
                    await websocket.send_json(
                        {
                            "type": "ack",
                            "message_id": len(self._stored_messages),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {client_id}")
            except Exception as e:
                logger.error(f"WebSocket error for {client_id}: {e}")
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except:
                    pass

    def _setup_routes(self):
        """Setup API routes."""

        @self._app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="healthy",
                personas_loaded=0,
                uptime_seconds=0.0,
                version="1.0.0",
            )

        @self._app.post("/chat", response_model=ChatResponse)
        async def chat(request: ChatRequest):
            """Synchronous chat endpoint."""
            message_data = {
                "message": request.message,
                "persona_id": request.persona_id,
                "user_id": request.user_id,
                "channel_id": request.channel_id,
                "context": request.context,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._stored_messages.append(message_data)
            return ChatResponse(
                response="Message received (processing not yet implemented)",
                persona_id=request.persona_id or "default",
                persona_name=request.persona_id or "default",
                timestamp=datetime.utcnow(),
                metadata={"stored": True, "pending": True},
            )

        @self._app.post("/chat/async")
        async def chat_async(
            request: ChatAsyncRequest, background_tasks: BackgroundTasks
        ):
            """Asynchronous chat endpoint - accepts message and returns immediately."""
            message_data = {
                "message": request.message,
                "persona_id": request.persona_id,
                "user_id": request.user_id,
                "channel_id": request.channel_id,
                "context": request.context,
                "webhook_url": request.webhook_url,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._stored_messages.append(message_data)
            return {
                "status": "accepted",
                "message_id": len(self._stored_messages) - 1,
                "webhook_url": request.webhook_url,
            }

        @self._app.get("/personas")
        async def list_personas():
            """List available personas."""
            return {"personas": []}

        @self._app.get("/messages")
        async def get_stored_messages():
            """Get stored messages for processing (for internal/debug use)."""
            return {
                "count": len(self._stored_messages),
                "messages": self._stored_messages,
            }

    async def start(self) -> None:
        """Start the web server."""
        if not FASTAPI_AVAILABLE:
            logger.error("Cannot start web adapter: FastAPI not installed")
            return

        if self._running:
            logger.warning("WebInputAdapter is already running")
            return

        self._running = True
        logger.info(f"Starting WebInputAdapter on {self.host}:{self.port}")

        # Run server in background
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
        """Register callback for incoming events."""
        self._event_callback = callback
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
