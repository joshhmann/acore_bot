"""Health check service for monitoring service availability.

T10: Production Infrastructure - Health Check Endpoints
Provides comprehensive health monitoring for all bot services.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthCheckService:
    """Service for checking health of all bot components.

    Features:
    - Individual service health checks with timeout protection
    - Response time tracking for each check
    - Cached results to avoid overwhelming services
    - Status levels: healthy, degraded, unhealthy
    """

    def __init__(self, cache_ttl: int = 30) -> None:
        """Initialize health check service.

        Args:
            cache_ttl: Cache TTL in seconds (default: 30)
        """
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, float] = {}

        # Service references (set after initialization)
        self.services: Dict[str, Any] = {}

    def register_services(self, services: Dict[str, Any]):
        """Register services for health monitoring.

        Args:
            services: Dict of service name to service instance
        """
        self.services = services
        logger.info(f"Registered {len(services)} services for health monitoring")

    def _is_cache_valid(self, service_name: str) -> bool:
        """Check if cached result is still valid.

        Args:
            service_name: Name of the service

        Returns:
            True if cache is valid
        """
        if service_name not in self.cache_timestamps:
            return False

        age = time.time() - self.cache_timestamps[service_name]
        return age < self.cache_ttl

    def _get_cached(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get cached health check result.

        Args:
            service_name: Name of the service

        Returns:
            Cached result or None
        """
        if self._is_cache_valid(service_name):
            return self.cache.get(service_name)
        return None

    def _set_cache(self, service_name: str, result: Dict[str, Any]):
        """Cache a health check result.

        Args:
            service_name: Name of the service
            result: Health check result
        """
        self.cache[service_name] = result
        self.cache_timestamps[service_name] = time.time()

    async def check_llm(self) -> Dict[str, Any]:
        """Check LLM service health.

        Returns:
            Health check result
        """
        service_name = "llm"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            ollama = self.services.get("ollama")
            if not ollama:
                result = {
                    "status": "unhealthy",
                    "response_time": 0,
                    "details": "LLM service not initialized",
                }
            else:
                # Check if service is available with timeout
                is_available = await asyncio.wait_for(
                    ollama.check_health(), timeout=5.0
                )

                response_time = (time.time() - start_time) * 1000  # ms

                if is_available:
                    model_name = (
                        ollama.get_model_name()
                        if hasattr(ollama, "get_model_name")
                        else "unknown"
                    )
                    result = {
                        "status": "healthy",
                        "response_time": round(response_time, 2),
                        "details": f"LLM service operational (model: {model_name})",
                    }
                else:
                    result = {
                        "status": "unhealthy",
                        "response_time": round(response_time, 2),
                        "details": "LLM service not responding",
                    }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "unhealthy",
                "response_time": round(response_time, 2),
                "details": "LLM health check timeout (5s)",
            }
            logger.warning("LLM health check timeout")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "unhealthy",
                "response_time": round(response_time, 2),
                "details": f"LLM health check error: {str(e)}",
            }
            logger.error(f"LLM health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_tts(self) -> Dict[str, Any]:
        """Check TTS service health.

        Returns:
            Health check result
        """
        service_name = "tts"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            tts = self.services.get("tts")
            if not tts:
                result = {
                    "status": "degraded",
                    "response_time": 0,
                    "details": "TTS service not initialized (optional)",
                }
            else:
                # Check if service is available with timeout
                is_available = await asyncio.wait_for(tts.is_available(), timeout=5.0)

                response_time = (time.time() - start_time) * 1000  # ms

                if is_available:
                    voice_info = tts.get_voice_info()
                    engine = voice_info.get("engine", "unknown")
                    result = {
                        "status": "healthy",
                        "response_time": round(response_time, 2),
                        "details": f"TTS service operational (engine: {engine})",
                    }
                else:
                    result = {
                        "status": "unhealthy",
                        "response_time": round(response_time, 2),
                        "details": "TTS service not available",
                    }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": "TTS health check timeout (5s)",
            }
            logger.warning("TTS health check timeout")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": f"TTS health check error: {str(e)}",
            }
            logger.error(f"TTS health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_rvc(self) -> Dict[str, Any]:
        """Check RVC service health.

        Returns:
            Health check result
        """
        service_name = "rvc"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            rvc = self.services.get("rvc")
            if not rvc:
                result = {
                    "status": "degraded",
                    "response_time": 0,
                    "details": "RVC service not initialized (optional)",
                }
            else:
                # Check if service is available with timeout
                is_available = await asyncio.wait_for(rvc.health_check(), timeout=5.0)

                response_time = (time.time() - start_time) * 1000  # ms

                if is_available:
                    result = {
                        "status": "healthy",
                        "response_time": round(response_time, 2),
                        "details": "RVC service operational",
                    }
                else:
                    result = {
                        "status": "degraded",
                        "response_time": round(response_time, 2),
                        "details": "RVC service not responding",
                    }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": "RVC health check timeout (5s)",
            }
            logger.warning("RVC health check timeout")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": f"RVC health check error: {str(e)}",
            }
            logger.error(f"RVC health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_rag(self) -> Dict[str, Any]:
        """Check RAG service health.

        Returns:
            Health check result
        """
        service_name = "rag"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            rag = self.services.get("rag")
            if not rag:
                result = {
                    "status": "degraded",
                    "response_time": 0,
                    "details": "RAG service not initialized (optional)",
                }
            else:
                # Check if service has documents loaded
                is_enabled = rag.is_enabled()

                response_time = (time.time() - start_time) * 1000  # ms

                if is_enabled:
                    stats = rag.get_stats()
                    doc_count = stats.get("total_documents", 0)
                    result = {
                        "status": "healthy",
                        "response_time": round(response_time, 2),
                        "details": f"RAG service operational ({doc_count} documents loaded)",
                    }
                else:
                    result = {
                        "status": "degraded",
                        "response_time": round(response_time, 2),
                        "details": "RAG service has no documents loaded",
                    }

        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": "RAG health check timeout (5s)",
            }
            logger.warning("RAG health check timeout")
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": f"RAG health check error: {str(e)}",
            }
            logger.error(f"RAG health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_memory(self) -> Dict[str, Any]:
        """Check memory services health (file system access).

        Returns:
            Health check result
        """
        service_name = "memory"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            from config import Config

            # Check if critical directories are accessible
            directories = [Config.CHAT_HISTORY_DIR, Config.DATA_DIR, Config.TEMP_DIR]

            all_accessible = True
            inaccessible = []

            for directory in directories:
                if not directory.exists():
                    all_accessible = False
                    inaccessible.append(str(directory))
                elif not directory.is_dir():
                    all_accessible = False
                    inaccessible.append(str(directory))

            response_time = (time.time() - start_time) * 1000  # ms

            if all_accessible:
                result = {
                    "status": "healthy",
                    "response_time": round(response_time, 2),
                    "details": "All memory directories accessible",
                }
            else:
                result = {
                    "status": "unhealthy",
                    "response_time": round(response_time, 2),
                    "details": f"Inaccessible directories: {', '.join(inaccessible)}",
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "unhealthy",
                "response_time": round(response_time, 2),
                "details": f"Memory health check error: {str(e)}",
            }
            logger.error(f"Memory health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_analytics(self) -> Dict[str, Any]:
        """Check analytics dashboard health.

        Returns:
            Health check result
        """
        service_name = "analytics"

        # Check cache first
        cached = self._get_cached(service_name)
        if cached:
            return cached

        start_time = time.time()

        try:
            from config import Config

            if not Config.ANALYTICS_DASHBOARD_ENABLED:
                result = {
                    "status": "degraded",
                    "response_time": 0,
                    "details": "Analytics dashboard disabled in config",
                }
            else:
                # Check if dashboard service exists and is enabled
                dashboard = self.services.get("analytics_dashboard")

                response_time = (time.time() - start_time) * 1000  # ms

                if dashboard and hasattr(dashboard, "enabled") and dashboard.enabled:
                    result = {
                        "status": "healthy",
                        "response_time": round(response_time, 2),
                        "details": f"Analytics dashboard running on port {Config.ANALYTICS_DASHBOARD_PORT}",
                    }
                else:
                    result = {
                        "status": "degraded",
                        "response_time": round(response_time, 2),
                        "details": "Analytics dashboard not initialized",
                    }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = {
                "status": "degraded",
                "response_time": round(response_time, 2),
                "details": f"Analytics health check error: {str(e)}",
            }
            logger.error(f"Analytics health check failed: {e}")

        self._set_cache(service_name, result)
        return result

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks in parallel.

        Returns:
            Combined health check results
        """
        # Run all checks in parallel
        results = await asyncio.gather(
            self.check_llm(),
            self.check_tts(),
            self.check_rvc(),
            self.check_rag(),
            self.check_memory(),
            self.check_analytics(),
            return_exceptions=True,
        )

        # Map results to service names
        service_names = ["llm", "tts", "rvc", "rag", "memory", "analytics"]
        health_results = {}

        for name, result in zip(service_names, results):
            if isinstance(result, Exception):
                health_results[name] = {
                    "status": "unhealthy",
                    "response_time": 0,
                    "details": f"Health check exception: {str(result)}",
                }
            else:
                health_results[name] = result

        # Determine overall status
        statuses = [r["status"] for r in health_results.values()]

        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        # Count by status
        healthy_count = sum(1 for s in statuses if s == "healthy")
        degraded_count = sum(1 for s in statuses if s == "degraded")
        unhealthy_count = sum(1 for s in statuses if s == "unhealthy")

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "services": health_results,
            "summary": {
                "total": len(service_names),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
            },
        }

    async def check_readiness(self) -> Dict[str, Any]:
        """Check if all critical services are operational.

        Critical services: LLM, Memory

        Returns:
            Readiness check result
        """
        # Check only critical services
        llm_result = await self.check_llm()
        memory_result = await self.check_memory()

        # System is ready if critical services are healthy
        critical_healthy = (
            llm_result["status"] == "healthy" and memory_result["status"] == "healthy"
        )

        return {
            "ready": critical_healthy,
            "timestamp": datetime.now().isoformat(),
            "critical_services": {"llm": llm_result, "memory": memory_result},
        }

    def get_simple_health(self) -> Dict[str, Any]:
        """Get simple alive check (synchronous).

        Returns:
            Simple health status
        """
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "Service is alive",
        }
