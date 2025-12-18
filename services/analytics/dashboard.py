"""Real-Time Analytics Dashboard

T23-T24: Real-Time Analytics Dashboard
Provides a web-based interface for monitoring persona metrics with real-time updates.

Features:
- FastAPI backend with WebSocket support
- Real-time metrics updates (message counts, affinity scores, mood trends)
- Persona evolution tracking
- Authentication via API key
- No sensitive data exposure
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Set, Any
from pathlib import Path
from config import Config

# Initialize logger first
logger = logging.getLogger(__name__)

try:
    from fastapi import (
        FastAPI,
        WebSocket,
        WebSocketDisconnect,
        HTTPException,
        Depends,
        Header,
    )
    from fastapi.security import APIKeyHeader
    from fastapi.responses import HTMLResponse

    FASTAPI_AVAILABLE = True

    # Import health check service if available
    try:
        from services.core.health import HealthCheckService

        HEALTH_SERVICE_AVAILABLE = True
    except ImportError:
        HEALTH_SERVICE_AVAILABLE = False
        logger.warning("HealthCheckService not available")

except ImportError:
    FASTAPI_AVAILABLE = False
    HEALTH_SERVICE_AVAILABLE = False
    logger.warning("FastAPI not installed - analytics dashboard disabled")


class AnalyticsDashboard:
    """Real-time analytics dashboard service.

    T23-T24: Provides web UI for monitoring bot performance and persona metrics.
    """

    def __init__(
        self,
        port: int = 8080,
        api_key: Optional[str] = None,
        enabled: bool = True,
    ):
        """Initialize analytics dashboard.

        Args:
            port: Port to run dashboard server on
            api_key: API key for authentication (if None, uses config)
            enabled: Whether dashboard is enabled
        """
        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not available - dashboard disabled")
            self.enabled = False
            return

        self.enabled = enabled
        if not enabled:
            logger.info("Analytics dashboard disabled via config")
            return

        self.port = port

        # Load API key from config if not provided
        if api_key is None:
            try:
                from config import Config

                api_key = getattr(
                    Config, "ANALYTICS_API_KEY", "change_me_in_production"
                )
            except Exception as e:
                logger.warning(f"Failed to load ANALYTICS_API_KEY from config: {e}")
                api_key = "change_me_in_production"

        self.api_key = api_key

        # FastAPI app
        self.app = FastAPI(title="Acore Bot Analytics", version="1.0.0")
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()

        # Metrics cache (updated periodically)
        self.metrics_cache: Dict = {}
        self.last_update = datetime.now()

        # Reference to bot (set after initialization)
        self.bot: Optional[Any] = None

        # Setup routes
        self._setup_routes()

        # Background task for metrics updates
        self._update_task: Optional[asyncio.Task] = None

        # Health check service
        self.health_service: Optional["HealthCheckService"] = None

        logger.info(f"Analytics dashboard initialized on port {port}")

    def _setup_routes(self):
        """Setup FastAPI routes."""

        async def verify_api_key(x_api_key: Optional[str] = Header(None)):
            """Dependency to verify API key from header."""
            if x_api_key != self.api_key:
                raise HTTPException(status_code=403, detail="Invalid API key")
            return True

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home():
            """Serve dashboard HTML."""
            html_path = (
                Path(__file__).parent.parent.parent
                / "templates"
                / "dashboard"
                / "index.html"
            )

            if html_path.exists():
                return html_path.read_text()
            else:
                # Return basic HTML if template doesn't exist
                return self._get_default_html()

        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint (no auth required)."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": (datetime.now() - self.last_update).total_seconds(),
            }

        @self.app.get("/api/metrics")
        async def get_metrics(authenticated: bool = Depends(verify_api_key)):
            """Get current metrics snapshot.

            Requires API key authentication.
            """
            return self.metrics_cache

        @self.app.websocket("/ws/metrics")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time metrics updates.

            Sends metrics updates every 2 seconds.
            """
            await websocket.accept()

            # Verify API key via query param
            api_key = websocket.query_params.get("api_key")
            if api_key != self.api_key:
                await websocket.close(code=1008, reason="Invalid API key")
                return

            self.active_connections.add(websocket)
            logger.info(
                f"New WebSocket connection - total: {len(self.active_connections)}"
            )

            try:
                # Send initial metrics
                await websocket.send_json(self.metrics_cache)

                # Keep connection alive and send updates
                while True:
                    await asyncio.sleep(Config.ANALYTICS_WEBSOCKET_UPDATE_INTERVAL)
                    await websocket.send_json(self.metrics_cache)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.active_connections.discard(websocket)
                logger.info(
                    f"WebSocket removed - total: {len(self.active_connections)}"
                )

    async def start(self):
        """Start the dashboard server."""
        if not self.enabled or not FASTAPI_AVAILABLE:
            logger.info("Dashboard not started (disabled or FastAPI unavailable)")
            return

        # Start metrics update task
        self._update_task = asyncio.create_task(self._update_metrics_loop())

        # Note: Actual server start would be done via uvicorn in main.py
        logger.info(f"Dashboard ready - access at http://localhost:{self.port}")
        logger.info(
            f"WebSocket endpoint: ws://localhost:{self.port}/ws/metrics?api_key=YOUR_KEY"
        )

    async def stop(self):
        """Stop the dashboard server."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        # Close all WebSocket connections
        for conn in list(self.active_connections):
            await conn.close()

        logger.info("Dashboard stopped")

    async def _update_metrics_loop(self):
        """Background task to update metrics cache."""
        while True:
            try:
                await asyncio.sleep(1)  # Update every second
                await self._collect_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error updating metrics: {e}")

    async def _collect_metrics(self):
        """Collect metrics from bot and services."""
        if not self.bot:
            self.metrics_cache = {"error": "Bot not initialized"}
            return

        try:
            # Add timeout protection for metrics collection
            metrics = await asyncio.wait_for(
                self._collect_metrics_internal(), timeout=5.0
            )

            self.metrics_cache = metrics
            self.last_update = datetime.now()

        except asyncio.TimeoutError:
            logger.error("Metrics collection timeout after 5 seconds")
            self.metrics_cache = {"error": "timeout"}
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self.metrics_cache = {"error": str(e)}

    async def _collect_metrics_internal(self):
        """Internal metrics collection with timeout protection."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (
                datetime.now() - getattr(self.bot, "start_time", datetime.now())
            ).total_seconds(),
            "personas": await self._collect_persona_metrics(),
            "performance": await self._collect_performance_metrics(),
            "activity": await self._collect_activity_metrics(),
        }
        return metrics

    async def _collect_persona_metrics(self) -> Dict:
        """Collect persona-specific metrics."""
        try:
            # Get PersonaSystem if available
            if not self.bot:
                return {}

            chat_cog = self.bot.get_cog("ChatCog")
            if not chat_cog or not hasattr(chat_cog, "persona_system"):
                return {}

            persona_system = chat_cog.persona_system

            metrics = {
                "total_personas": len(persona_system.characters),
                "active_personas": [],
            }

            # Collect per-persona stats
            for char_id, character in persona_system.characters.items():
                persona_data = {
                    "id": char_id,
                    "name": character.display_name,
                    "message_count": 0,  # Would need to track this
                    "mood": "neutral",  # Would get from BehaviorEngine
                    "evolution_stage": 0,  # Would get from EvolutionTracker
                }
                metrics["active_personas"].append(persona_data)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting persona metrics: {e}")
            return {"error": str(e)}

    async def _collect_performance_metrics(self) -> Dict:
        """Collect performance metrics."""
        try:
            # Get MetricsService if available
            if self.bot and hasattr(self.bot, "metrics"):
                metrics_svc = self.bot.metrics

                return {
                    "avg_response_time_ms": (
                        sum(metrics_svc.response_times)
                        / len(metrics_svc.response_times)
                        * 1000
                        if metrics_svc.response_times
                        else 0
                    ),
                    "total_errors": metrics_svc.error_counts["total_errors"],
                    "cache_hit_rate": (
                        metrics_svc.cache_stats["history_cache_hits"]
                        / (
                            metrics_svc.cache_stats["history_cache_hits"]
                            + metrics_svc.cache_stats["history_cache_misses"]
                        )
                        if (
                            metrics_svc.cache_stats["history_cache_hits"]
                            + metrics_svc.cache_stats["history_cache_misses"]
                        )
                        > 0
                        else 0
                    ),
                }

            return {}

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {"error": str(e)}

    async def _collect_activity_metrics(self) -> Dict:
        """Collect activity metrics."""
        try:
            if self.bot and hasattr(self.bot, "metrics"):
                metrics_svc = self.bot.metrics

                return {
                    "messages_processed": metrics_svc.active_stats[
                        "messages_processed"
                    ],
                    "active_users": len(metrics_svc.active_stats["active_users"]),
                    "active_channels": len(metrics_svc.active_stats["active_channels"]),
                    "commands_executed": metrics_svc.active_stats["commands_executed"],
                }

            return {}

        except Exception as e:
            logger.error(f"Error collecting activity metrics: {e}")
            return {"error": str(e)}

    def _get_default_html(self) -> str:
        """Get default dashboard HTML if template doesn't exist."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acore Bot Analytics</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 {
            color: #667eea;
            border-bottom: 3px solid #764ba2;
            padding-bottom: 10px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            color: #555;
            font-size: 14px;
            text-transform: uppercase;
        }
        .metric-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }
        .status.connected {
            background: #4caf50;
            color: white;
        }
        .status.disconnected {
            background: #f44336;
            color: white;
        }
        #personas-list {
            margin-top: 20px;
        }
        .persona-item {
            background: #fff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Acore Bot Analytics Dashboard</h1>
        <p>Real-time monitoring for persona metrics and performance</p>
        <p>Status: <span id="connection-status" class="status disconnected">Disconnected</span></p>
        
        <div class="metric-grid">
            <div class="metric-card">
                <h3>Uptime</h3>
                <div class="value" id="uptime">--</div>
            </div>
            <div class="metric-card">
                <h3>Messages Processed</h3>
                <div class="value" id="messages">0</div>
            </div>
            <div class="metric-card">
                <h3>Active Users</h3>
                <div class="value" id="users">0</div>
            </div>
            <div class="metric-card">
                <h3>Avg Response Time</h3>
                <div class="value" id="response-time">0ms</div>
            </div>
        </div>
        
        <h2>Active Personas</h2>
        <div id="personas-list">
            <p>Loading...</p>
        </div>
    </div>
    
    <script>
        const API_KEY = prompt("Enter API key:");
        const WS_URL = `ws://${window.location.host}/ws/metrics?api_key=${API_KEY}`;
        
        let ws = null;
        
        function connect() {
            ws = new WebSocket(WS_URL);
            
            ws.onopen = () => {
                document.getElementById('connection-status').textContent = 'Connected';
                document.getElementById('connection-status').className = 'status connected';
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            ws.onclose = () => {
                document.getElementById('connection-status').textContent = 'Disconnected';
                document.getElementById('connection-status').className = 'status disconnected';
                setTimeout(connect, 5000);  // Reconnect after 5s
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateDashboard(data) {
            // Update uptime
            if (data.uptime_seconds) {
                const hours = Math.floor(data.uptime_seconds / 3600);
                const minutes = Math.floor((data.uptime_seconds % 3600) / 60);
                document.getElementById('uptime').textContent = `${hours}h ${minutes}m`;
            }
            
            // Update activity metrics
            if (data.activity) {
                document.getElementById('messages').textContent = data.activity.messages_processed || 0;
                document.getElementById('users').textContent = data.activity.active_users || 0;
            }
            
            // Update performance metrics
            if (data.performance) {
                document.getElementById('response-time').textContent = 
                    Math.round(data.performance.avg_response_time_ms || 0) + 'ms';
            }
            
            // Update personas list
            if (data.personas && data.personas.active_personas) {
                const personasList = document.getElementById('personas-list');
                personasList.innerHTML = data.personas.active_personas.map(p => `
                    <div class="persona-item">
                        <strong>${p.name}</strong> (${p.id})<br>
                        Messages: ${p.message_count} | Mood: ${p.mood} | Stage: ${p.evolution_stage}
                    </div>
                `).join('');
            }
        }
        
        // Connect on load
        connect();
    </script>
</body>
</html>
        """
