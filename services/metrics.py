"""Metrics tracking service for monitoring bot performance and usage."""
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for tracking bot metrics and analytics."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize metrics service.

        Args:
            data_dir: Directory to store metrics logs
        """
        # Set up metrics data directory
        if data_dir is None:
            from config import Config
            data_dir = Config.DATA_DIR / "metrics"

        self.metrics_dir = Path(data_dir)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # Check if DEBUG mode for enhanced logging
        from config import Config
        self.debug_mode = Config.LOG_LEVEL == "DEBUG"

        # Response time tracking (rolling window of last 100 responses in INFO, 500 in DEBUG)
        max_history = 500 if self.debug_mode else 100
        self.response_times = deque(maxlen=max_history)

        # DEBUG MODE: Detailed request log (last 100 requests with full details)
        self.detailed_requests = deque(maxlen=100) if self.debug_mode else None

        # Token usage tracking
        self.token_usage = {
            'total_tokens': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'by_model': defaultdict(int),
        }

        # Error tracking
        self.error_counts = {
            'total_errors': 0,
            'by_type': defaultdict(int),
            'recent_errors': deque(maxlen=20),  # Last 20 errors with timestamps
        }

        # Active tracking (reset hourly to prevent unbounded growth)
        self.active_stats = {
            'active_users': set(),
            'active_channels': set(),
            'messages_processed': 0,
            'commands_executed': 0,
        }
        self._last_active_reset = datetime.now()
        self._reset_task: Optional[asyncio.Task] = None

        # Cache hit rates
        self.cache_stats = {
            'history_cache_hits': 0,
            'history_cache_misses': 0,
            'rag_cache_hits': 0,
            'rag_cache_misses': 0,
        }

        # Service-specific metrics
        self.service_metrics = {
            'tts_generations': 0,
            'vision_requests': 0,
            'web_searches': 0,
            'summarizations': 0,
            'rag_queries': 0,
        }

        # Hourly stats (for trending)
        self.hourly_stats = {
            'messages_per_hour': deque(maxlen=24),  # Last 24 hours
            'errors_per_hour': deque(maxlen=24),
            'last_hour_start': datetime.now(),
            'current_hour_messages': 0,
            'current_hour_errors': 0,
        }

        # Start time
        self.start_time = datetime.now()

        logger.info("Metrics service initialized")

    # Response time tracking
    def record_response_time(self, duration_ms: float, details: Optional[Dict] = None):
        """Record a response time.

        Args:
            duration_ms: Response time in milliseconds
            details: Optional detailed information (used in DEBUG mode)
        """
        self.response_times.append(duration_ms)

        # In DEBUG mode, record detailed request info
        if self.debug_mode and self.detailed_requests is not None and details:
            request_log = {
                'timestamp': datetime.now().isoformat(),
                'duration_ms': duration_ms,
                **details  # Include all provided details
            }
            self.detailed_requests.append(request_log)

    def get_response_time_stats(self) -> Dict:
        """Get response time statistics.

        Returns:
            Dict with avg, min, max, p50, p95, p99
        """
        if not self.response_times:
            return {
                'avg': 0,
                'min': 0,
                'max': 0,
                'p50': 0,
                'p95': 0,
                'p99': 0,
                'count': 0,
            }

        sorted_times = sorted(self.response_times)
        count = len(sorted_times)

        return {
            'avg': sum(sorted_times) / count,
            'min': sorted_times[0],
            'max': sorted_times[-1],
            'p50': sorted_times[int(count * 0.50)],
            'p95': sorted_times[int(count * 0.95)] if count > 1 else sorted_times[0],
            'p99': sorted_times[int(count * 0.99)] if count > 1 else sorted_times[0],
            'count': count,
        }

    # Token usage tracking
    def record_token_usage(self, prompt_tokens: int, completion_tokens: int, model: str = "unknown"):
        """Record token usage.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: Model name
        """
        total = prompt_tokens + completion_tokens
        self.token_usage['total_tokens'] += total
        self.token_usage['prompt_tokens'] += prompt_tokens
        self.token_usage['completion_tokens'] += completion_tokens
        self.token_usage['by_model'][model] += total

    def get_token_usage(self) -> Dict:
        """Get token usage statistics.

        Returns:
            Token usage stats
        """
        return {
            'total_tokens': self.token_usage['total_tokens'],
            'prompt_tokens': self.token_usage['prompt_tokens'],
            'completion_tokens': self.token_usage['completion_tokens'],
            'by_model': dict(self.token_usage['by_model']),
        }

    # Error tracking
    def record_error(self, error_type: str, error_message: str):
        """Record an error.

        Args:
            error_type: Type of error (e.g., 'APIError', 'ValidationError')
            error_message: Error message
        """
        self.error_counts['total_errors'] += 1
        self.error_counts['by_type'][error_type] += 1
        self.error_counts['recent_errors'].append({
            'type': error_type,
            'message': error_message[:200],  # Truncate long messages
            'timestamp': datetime.now().isoformat(),
        })
        self.hourly_stats['current_hour_errors'] += 1

    def get_error_stats(self) -> Dict:
        """Get error statistics.

        Returns:
            Error stats
        """
        return {
            'total_errors': self.error_counts['total_errors'],
            'by_type': dict(self.error_counts['by_type']),
            'recent_errors': list(self.error_counts['recent_errors']),
            'error_rate': self._calculate_error_rate(),
        }

    def _calculate_error_rate(self) -> float:
        """Calculate error rate (errors per message).

        Returns:
            Error rate as percentage
        """
        total_messages = self.active_stats['messages_processed']
        if total_messages == 0:
            return 0.0
        return (self.error_counts['total_errors'] / total_messages) * 100

    # Active stats tracking
    def record_message(self, user_id: int, channel_id: int):
        """Record a message being processed.

        Args:
            user_id: User ID
            channel_id: Channel ID
        """
        self.active_stats['active_users'].add(user_id)
        self.active_stats['active_channels'].add(channel_id)
        self.active_stats['messages_processed'] += 1
        self.hourly_stats['current_hour_messages'] += 1
        self._check_hourly_rollover()

    def record_command(self, command_name: str):
        """Record a command execution.

        Args:
            command_name: Name of the command
        """
        self.active_stats['commands_executed'] += 1

    def get_active_stats(self) -> Dict:
        """Get active user/channel statistics.

        Returns:
            Active stats
        """
        return {
            'active_users': len(self.active_stats['active_users']),
            'active_channels': len(self.active_stats['active_channels']),
            'messages_processed': self.active_stats['messages_processed'],
            'commands_executed': self.active_stats['commands_executed'],
        }

    # Cache stats tracking
    def record_cache_hit(self, cache_type: str):
        """Record a cache hit.

        Args:
            cache_type: Type of cache ('history', 'rag', etc.)
        """
        key = f"{cache_type}_cache_hits"
        if key in self.cache_stats:
            self.cache_stats[key] += 1

    def record_cache_miss(self, cache_type: str):
        """Record a cache miss.

        Args:
            cache_type: Type of cache ('history', 'rag', etc.)
        """
        key = f"{cache_type}_cache_misses"
        if key in self.cache_stats:
            self.cache_stats[key] += 1

    def get_cache_stats(self) -> Dict:
        """Get cache hit rate statistics.

        Returns:
            Cache stats with hit rates
        """
        def calculate_hit_rate(hits: int, misses: int) -> float:
            total = hits + misses
            return (hits / total * 100) if total > 0 else 0.0

        return {
            'history_cache': {
                'hits': self.cache_stats['history_cache_hits'],
                'misses': self.cache_stats['history_cache_misses'],
                'hit_rate': calculate_hit_rate(
                    self.cache_stats['history_cache_hits'],
                    self.cache_stats['history_cache_misses']
                ),
            },
            'rag_cache': {
                'hits': self.cache_stats['rag_cache_hits'],
                'misses': self.cache_stats['rag_cache_misses'],
                'hit_rate': calculate_hit_rate(
                    self.cache_stats['rag_cache_hits'],
                    self.cache_stats['rag_cache_misses']
                ),
            },
        }

    # Service-specific metrics
    def record_service_event(self, service: str, event: str = 'request'):
        """Record a service event.

        Args:
            service: Service name ('tts', 'vision', 'web_search', etc.)
            event: Event type (default: 'request')
        """
        key = f"{service}_{event}s"
        if key in self.service_metrics:
            self.service_metrics[key] += 1

    def get_service_metrics(self) -> Dict:
        """Get service-specific metrics.

        Returns:
            Service metrics
        """
        return dict(self.service_metrics)

    # Hourly stats
    def _check_hourly_rollover(self):
        """Check if we need to rollover to a new hour."""
        now = datetime.now()
        if now - self.hourly_stats['last_hour_start'] >= timedelta(hours=1):
            # Save current hour stats
            self.hourly_stats['messages_per_hour'].append(
                self.hourly_stats['current_hour_messages']
            )
            self.hourly_stats['errors_per_hour'].append(
                self.hourly_stats['current_hour_errors']
            )

            # Reset for new hour
            self.hourly_stats['current_hour_messages'] = 0
            self.hourly_stats['current_hour_errors'] = 0
            self.hourly_stats['last_hour_start'] = now

    def get_hourly_trends(self) -> Dict:
        """Get hourly trend data.

        Returns:
            Hourly trends
        """
        return {
            'messages_per_hour': list(self.hourly_stats['messages_per_hour']),
            'errors_per_hour': list(self.hourly_stats['errors_per_hour']),
            'current_hour_messages': self.hourly_stats['current_hour_messages'],
            'current_hour_errors': self.hourly_stats['current_hour_errors'],
        }

    # Overall summary
    def get_summary(self) -> Dict:
        """Get complete metrics summary.

        Returns:
            Complete metrics summary
        """
        uptime = datetime.now() - self.start_time

        summary = {
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_formatted': str(uptime).split('.')[0],  # Remove microseconds
            'response_times': self.get_response_time_stats(),
            'token_usage': self.get_token_usage(),
            'errors': self.get_error_stats(),
            'active_stats': self.get_active_stats(),
            'cache_stats': self.get_cache_stats(),
            'service_metrics': self.get_service_metrics(),
            'hourly_trends': self.get_hourly_trends(),
            'debug_mode': self.debug_mode,
        }

        # Include detailed request log in DEBUG mode
        if self.debug_mode and self.detailed_requests is not None:
            summary['detailed_requests'] = list(self.detailed_requests)
            summary['detailed_request_count'] = len(self.detailed_requests)

        return summary

    # Helper context manager for timing operations
    class Timer:
        """Context manager for timing operations."""

        def __init__(self, metrics_service: 'MetricsService'):
            """Initialize timer.

            Args:
                metrics_service: MetricsService instance
            """
            self.metrics_service = metrics_service
            self.start_time = None

        def __enter__(self):
            """Start timer."""
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Stop timer and record."""
            duration_ms = (time.time() - self.start_time) * 1000
            self.metrics_service.record_response_time(duration_ms)
            return False

    def timer(self):
        """Get a timer context manager.

        Returns:
            Timer context manager

        Usage:
            with metrics.timer():
                # Your code here
                pass
        """
        return self.Timer(self)

    # Metrics persistence
    def save_metrics_to_file(self, filename: Optional[str] = None):
        """Save current metrics to a JSON file.

        Args:
            filename: Optional custom filename. If None, uses timestamp.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.json"

        filepath = self.metrics_dir / filename

        try:
            # Get complete metrics summary
            metrics_data = self.get_summary()

            # Add metadata
            metrics_data['saved_at'] = datetime.now().isoformat()
            metrics_data['version'] = '1.0'

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)

            logger.info(f"Metrics saved to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            return None

    def save_hourly_snapshot(self):
        """Save hourly metrics snapshot.

        Creates a file named metrics_YYYYMMDD_HH.json
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        filename = f"hourly_{timestamp}.json"
        return self.save_metrics_to_file(filename)

    def save_daily_summary(self):
        """Save daily metrics summary.

        Creates a file named metrics_YYYYMMDD.json
        """
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"daily_{timestamp}.json"
        return self.save_metrics_to_file(filename)

    def cleanup_old_metrics(self, days_to_keep: int = 30):
        """Clean up old metrics files.

        Args:
            days_to_keep: Number of days of metrics to keep (default: 30)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            deleted = 0

            for file in self.metrics_dir.glob("*.json"):
                # Check file modification time
                file_time = datetime.fromtimestamp(file.stat().st_mtime)
                if file_time < cutoff_date:
                    file.unlink()
                    deleted += 1
                    logger.debug(f"Deleted old metrics file: {file.name}")

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old metrics files")

        except Exception as e:
            logger.error(f"Failed to cleanup metrics: {e}")

    def start_auto_save(self, interval_hours: int = 1):
        """Start automatic metrics saving task.

        Args:
            interval_hours: Hours between saves (default: 1)

        Returns:
            Async task
        """
        async def auto_save_loop():
            while True:
                try:
                    await asyncio.sleep(interval_hours * 3600)
                    self.save_hourly_snapshot()

                    # Daily cleanup at midnight
                    now = datetime.now()
                    if now.hour == 0:
                        self.save_daily_summary()
                        # Use configured retention period
                        from config import Config
                        self.cleanup_old_metrics(days_to_keep=Config.METRICS_RETENTION_DAYS)

                except Exception as e:
                    logger.error(f"Error in auto-save loop: {e}")

        return asyncio.create_task(auto_save_loop())

    def start_hourly_reset(self):
        """Start background task to reset active stats hourly (prevents memory leak).

        Returns:
            The background task
        """
        if self._reset_task and not self._reset_task.done():
            logger.warning("Hourly reset task already running")
            return self._reset_task

        async def hourly_reset_loop():
            """Reset active user/channel sets every hour to prevent unbounded growth."""
            while True:
                try:
                    await asyncio.sleep(3600)  # 1 hour

                    # Log stats before reset
                    user_count = len(self.active_stats['active_users'])
                    channel_count = len(self.active_stats['active_channels'])
                    logger.info(
                        f"Hourly active stats reset: {user_count} users, "
                        f"{channel_count} channels in last hour"
                    )

                    # Reset unbounded sets
                    self.active_stats['active_users'].clear()
                    self.active_stats['active_channels'].clear()
                    self._last_active_reset = datetime.now()

                except Exception as e:
                    logger.error(f"Error in hourly reset loop: {e}")

        self._reset_task = asyncio.create_task(hourly_reset_loop())
        logger.info("Started hourly active stats reset task")
        return self._reset_task

    def load_metrics_from_file(self, filename: str) -> Optional[Dict]:
        """Load metrics from a file.

        Args:
            filename: Filename to load

        Returns:
            Metrics dictionary or None
        """
        filepath = self.metrics_dir / filename

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded metrics from {filepath}")
            return data

        except Exception as e:
            logger.error(f"Failed to load metrics from {filename}: {e}")
            return None

    def list_saved_metrics(self) -> List[Dict]:
        """List all saved metrics files.

        Returns:
            List of dicts with filename, size, and timestamp
        """
        metrics_files = []

        for file in sorted(self.metrics_dir.glob("*.json"), reverse=True):
            try:
                stat = file.stat()
                metrics_files.append({
                    'filename': file.name,
                    'size_bytes': stat.st_size,
                    'size_kb': round(stat.st_size / 1024, 2),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception as e:
                logger.warning(f"Failed to stat {file}: {e}")

        return metrics_files
