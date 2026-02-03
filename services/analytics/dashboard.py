"""Real-Time Analytics Dashboard

T23-T24: Real-Time Analytics Dashboard
Provides a web-based interface for monitoring persona metrics with real-time updates.

Features:
- FastAPI backend with WebSocket support
- Real-time metrics updates (message counts, affinity scores, mood trends)
- Persona evolution tracking
- Authentication via API key
- No sensitive data exposure
- Configuration management dashboard
"""

import asyncio
import logging
import os
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

    # ============ Configuration Management Helpers ============

    def _mask_value(self, value: str) -> dict:
        """Mask a value for display, showing only first/last chars."""
        if not value:
            return {"masked": False, "value": ""}
        if len(value) <= 4:
            return {"masked": True, "value": "****"}
        return {
            "masked": True,
            "value": value[:2] + "****" + value[-2:],
        }

    def _check_service_health(self, url: str) -> bool:
        """Check if a service is reachable."""
        try:
            import urllib.request

            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    def _update_env_file(self, key: str, value: str) -> bool:
        """Update a key in the .env file."""
        try:
            env_path = Path(".env")
            if not env_path.exists():
                return False

            lines = env_path.read_text().splitlines()
            updated = False
            new_lines = []

            for line in lines:
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={value}")
                    updated = True
                else:
                    new_lines.append(line)

            if not updated:
                new_lines.append(f"{key}={value}")

            env_path.write_text("\n".join(new_lines))
            return True
        except Exception as e:
            logger.error(f"Failed to update .env: {e}")
            return False

    def _regenerate_env_from_config(self) -> bool:
        """Regenerate .env file with documented comments."""
        try:
            env_path = Path(".env")
            backup_path = Path(".env.backup")

            if env_path.exists():
                backup_path.write_text(env_path.read_text())

            template = """# Acore Bot Configuration
# Generated by Analytics Dashboard

# Discord
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_PREFIX=!

# LLM Provider (openrouter, ollama)
LLM_PROVIDER=openrouter

# OpenRouter (for DALL-E and cloud LLM)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=x-ai/grok-3-fast

# Image Generation
IMAGE_GENERATION_ENABLED=true
IMAGE_PROVIDER=comfyui  # openai, replicate, comfyui, litellm, koboldcpp
IMAGE_SIZE_DEFAULT=1024x1024

# ComfyUI (local SD)
COMFYUI_SERVER_URL=http://127.0.0.1:8188

# KoboldCPP (local SD)
KOBOLDCPP_URL=http://127.0.0.1:5001
KOBOLDCPP_STEPS=30

# LiteLLM Proxy
LITELLM_BASE_URL=http://localhost:4000
LITELLM_IMAGE_MODEL=dall-e-3

# RAG & Memory
RAG_ENABLED=true
RAG_HYBRID_SEARCH_ENABLED=true
RAG_RERANKER_ENABLED=true

# Agents
AGENT_ROUTING_ENABLED=true
USE_FUNCTION_CALLING=false

# Voice
TTS_ENGINE=kokoro_api
RVC_ENABLED=false

# Analytics
ANALYTICS_DASHBOARD_ENABLED=true
ANALYTICS_DASHBOARD_PORT=8080
ANALYTICS_API_KEY=change_this_in_production
"""
            env_path.write_text(template)
            return True
        except Exception as e:
            logger.error(f"Failed to regenerate .env: {e}")
            return False

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

        # ============ Configuration Management Endpoints ============

        @self.app.get("/api/config")
        async def get_config(authenticated: bool = Depends(verify_api_key)):
            """Get current configuration (safe fields only, no secrets)."""
            from config import Config

            config_data = {
                "categories": {
                    "General": {
                        "DISCORD_TOKEN_SET": bool(Config.DISCORD_TOKEN),
                        "LLM_PROVIDER": getattr(Config, "LLM_PROVIDER", "openrouter"),
                        "ACTIVE_PERSONAS": getattr(Config, "ACTIVE_PERSONAS", []),
                    },
                    "Image Generation": {
                        "IMAGE_GENERATION_ENABLED": Config.IMAGE_GENERATION_ENABLED,
                        "IMAGE_PROVIDER": Config.IMAGE_PROVIDER,
                        "IMAGE_SIZE_DEFAULT": Config.IMAGE_SIZE_DEFAULT,
                    },
                    "RAG & Memory": {
                        "RAG_ENABLED": getattr(Config, "RAG_ENABLED", True),
                        "RAG_HYBRID_SEARCH_ENABLED": Config.RAG_HYBRID_SEARCH_ENABLED,
                        "RAG_RERANKER_ENABLED": Config.RAG_RERANKER_ENABLED,
                        "USER_PROFILES_ENABLED": Config.USER_PROFILES_ENABLED,
                    },
                    "Agents": {
                        "AGENT_ROUTING_ENABLED": Config.AGENT_ROUTING_ENABLED,
                        "USE_FUNCTION_CALLING": getattr(
                            Config, "USE_FUNCTION_CALLING", False
                        ),
                    },
                    "Voice": {
                        "TTS_ENGINE": Config.TTS_ENGINE,
                        "RVC_ENABLED": Config.RVC_ENABLED,
                    },
                    "Analytics": {
                        "ANALYTICS_DASHBOARD_ENABLED": getattr(
                            Config, "ANALYTICS_DASHBOARD_ENABLED", True
                        ),
                    },
                },
                "api_keys_status": {
                    "OPENAI_API_KEY": self._mask_value(Config.OPENROUTER_API_KEY),
                    "REPLICATE_API_KEY": self._mask_value(
                        os.getenv("REPLICATE_API_KEY", "")
                    ),
                    "COMFYUI_SERVER_URL": Config.COMFYUI_SERVER_URL,
                    "KOBOLDCPP_URL": Config.KOBOLDCPP_URL,
                    "LITELLM_BASE_URL": Config.LITELLM_BASE_URL,
                },
                "config_file_path": str(Path(".env")),
            }
            return config_data

        @self.app.get("/api/config/providers/image")
        async def get_image_providers(authenticated: bool = Depends(verify_api_key)):
            """Get available image generation providers and their status."""
            providers = {
                "openai": {
                    "name": "DALL-E 3 (OpenAI)",
                    "description": "High-quality cloud image generation",
                    "requires_api_key": True,
                    "features": ["txt2img", "edit", "variations"],
                    "configured": bool(Config.OPENROUTER_API_KEY),
                },
                "replicate": {
                    "name": "Stable Diffusion (Replicate)",
                    "description": "Open source models via cloud API",
                    "requires_api_key": True,
                    "features": ["txt2img"],
                    "configured": bool(os.getenv("REPLICATE_API_KEY", "")),
                },
                "comfyui": {
                    "name": "ComfyUI (Local)",
                    "description": "Full Stable Diffusion workflows on your machine",
                    "requires_api_key": False,
                    "features": ["txt2img", "custom_workflows", "img2img"],
                    "url": Config.COMFYUI_SERVER_URL,
                    "configured": self._check_service_health(Config.COMFYUI_SERVER_URL),
                },
                "litellm": {
                    "name": "LiteLLM (Proxy)",
                    "description": "Unified API for multiple image backends",
                    "requires_api_key": False,
                    "features": ["txt2img"],
                    "url": Config.LITELLM_BASE_URL,
                    "configured": bool(Config.LITELLM_BASE_URL),
                },
                "koboldcpp": {
                    "name": "KoboldCPP (Local)",
                    "description": "Local Stable Diffusion with img2img support",
                    "requires_api_key": False,
                    "features": ["txt2img", "img2img", "inpaint"],
                    "url": Config.KOBOLDCPP_URL,
                    "configured": self._check_service_health(Config.KOBOLDCPP_URL),
                },
            }
            return {"providers": providers, "current_provider": Config.IMAGE_PROVIDER}

        @self.app.post("/api/config/image-provider")
        async def set_image_provider(
            body: dict, authenticated: bool = Depends(verify_api_key)
        ):
            """Set the active image generation provider."""
            provider = body.get("provider")
            valid_providers = ["openai", "replicate", "comfyui", "litellm", "koboldcpp"]
            if provider not in valid_providers:
                return {"success": False, "error": f"Invalid provider: {provider}"}

            success = self._update_env_file("IMAGE_PROVIDER", provider)
            if success:
                return {"success": True, "message": f"Provider set to {provider}"}
            return {"success": False, "error": "Failed to update .env file"}

        @self.app.post("/api/config/toggle")
        async def toggle_feature(
            body: dict, authenticated: bool = Depends(verify_api_key)
        ):
            """Toggle a feature on/off."""
            feature = body.get("feature")
            enabled = body.get("enabled")

            feature_map = {
                "IMAGE_GENERATION_ENABLED": "IMAGE_GENERATION_ENABLED",
                "RAG_HYBRID_SEARCH_ENABLED": "RAG_HYBRID_SEARCH_ENABLED",
                "AGENT_ROUTING_ENABLED": "AGENT_ROUTING_ENABLED",
                "USE_FUNCTION_CALLING": "USE_FUNCTION_CALLING",
                "RVC_ENABLED": "RVC_ENABLED",
            }

            env_key = feature_map.get(feature)
            if not env_key:
                return {"success": False, "error": f"Unknown feature: {feature}"}

            success = self._update_env_file(env_key, str(enabled).lower())
            if success:
                return {"success": True, "message": f"{feature} set to {enabled}"}
            return {"success": False, "error": "Failed to update .env file"}

        @self.app.get("/api/logs")
        async def get_recent_logs(
            lines: int = 100, authenticated: bool = Depends(verify_api_key)
        ):
            """Get recent log entries."""
            log_files = [
                Path("bot.log"),
                Path("/root/acore_bot/bot.log"),
            ]
            logs = []
            for log_file in log_files:
                if log_file.exists():
                    try:
                        with open(log_file, "r") as f:
                            lines_list = f.readlines()
                            logs.extend(lines_list[-lines:])
                    except Exception:
                        pass
            return {"logs": logs[-lines:] if len(logs) > lines else logs}

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
            "rl": await self._collect_rl_metrics(),
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

    async def _collect_rl_metrics(self) -> Dict:
        """Collect RL (Reinforcement Learning) metrics."""
        try:
            if not self.bot:
                return {"enabled": False}

            # Get RL service from bot services
            rl_service = None
            if hasattr(self.bot, "services"):
                rl_service = self.bot.services.get("rl")

            if not rl_service:
                return {"enabled": False}

            # Calculate aggregate metrics
            total_agents = len(rl_service.agents)
            total_states = 0
            avg_epsilon = 0.0
            avg_q_value = 0.0
            q_value_count = 0
            top_states = []

            if total_agents > 0:
                epsilons = []
                for agent in rl_service.agents.values():
                    epsilons.append(agent.epsilon)
                    total_states += len(agent.q_table)

                    # Collect Q-values for average
                    for state, q_row in agent.q_table.items():
                        for q_val in q_row.values():
                            avg_q_value += q_val
                            q_value_count += 1

                        # Track top states by max Q-value
                        max_q = max(q_row.values())
                        best_action = max(q_row.items(), key=lambda x: x[1])[0]
                        top_states.append(
                            {
                                "state": state,
                                "max_q": max_q,
                                "best_action": best_action.name,
                                "action_values": {a.name: v for a, v in q_row.items()},
                            }
                        )

                avg_epsilon = sum(epsilons) / len(epsilons)

                # Sort and keep top 10 states
                top_states.sort(key=lambda x: x["max_q"], reverse=True)
                top_states = top_states[:10]

            if q_value_count > 0:
                avg_q_value /= q_value_count

            return {
                "enabled": rl_service.enabled,
                "total_agents": total_agents,
                "total_states": total_states,
                "avg_epsilon": round(avg_epsilon, 4),
                "avg_q_value": round(avg_q_value, 2),
                "top_states": top_states,
            }

        except Exception as e:
            logger.error(f"Error collecting RL metrics: {e}")
            return {"enabled": False, "error": str(e)}

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
