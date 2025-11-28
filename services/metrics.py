"""Metrics tracking service for monitoring bot performance and usage."""
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for tracking bot metrics and analytics."""

    def __init__(self):
        """Initialize metrics service."""
        # Response time tracking (rolling window of last 100 responses)
        self.response_times = deque(maxlen=100)

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

        # Active tracking
        self.active_stats = {
            'active_users': set(),
            'active_channels': set(),
            'messages_processed': 0,
            'commands_executed': 0,
        }

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
    def record_response_time(self, duration_ms: float):
        """Record a response time.

        Args:
            duration_ms: Response time in milliseconds
        """
        self.response_times.append(duration_ms)

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

        return {
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_formatted': str(uptime).split('.')[0],  # Remove microseconds
            'response_times': self.get_response_time_stats(),
            'token_usage': self.get_token_usage(),
            'errors': self.get_error_stats(),
            'active_stats': self.get_active_stats(),
            'cache_stats': self.get_cache_stats(),
            'service_metrics': self.get_service_metrics(),
            'hourly_trends': self.get_hourly_trends(),
        }

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
