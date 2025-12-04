"""Rate limiting utilities to prevent API quota exhaustion."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with concurrency control and requests-per-minute limit.
    
    Features:
    - Limits concurrent requests (semaphore)
    - Limits requests per minute (sliding window)
    - Automatic wait when limits reached
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        requests_per_minute: int = 60,
        name: str = "RateLimiter"
    ):
        """Initialize rate limiter.
        
        Args:
            max_concurrent: Maximum concurrent requests allowed
            requests_per_minute: Maximum requests per 60-second window
            name: Name for logging identification
        """
        self.max_concurrent = max_concurrent
        self.requests_per_minute = requests_per_minute
        self.name = name
        
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_timestamps: list[float] = []
        self._lock = asyncio.Lock()
        
        # Stats
        self.total_requests = 0
        self.total_waits = 0
        self.total_wait_time = 0.0
        
        logger.info(
            f"RateLimiter '{name}' initialized: "
            f"max_concurrent={max_concurrent}, rpm={requests_per_minute}"
        )

    async def _check_rate_limit(self) -> Optional[float]:
        """Check if rate limit is exceeded and return wait time if so.
        
        Returns:
            Seconds to wait, or None if under limit
        """
        async with self._lock:
            now = time.time()
            
            # Remove timestamps older than 60 seconds
            self.request_timestamps = [
                ts for ts in self.request_timestamps 
                if now - ts < 60
            ]
            
            # Check if at limit
            if len(self.request_timestamps) >= self.requests_per_minute:
                # Calculate wait time until oldest request expires
                oldest = self.request_timestamps[0]
                wait_time = 60 - (now - oldest) + 0.1  # Small buffer
                return max(0.1, wait_time)
            
            return None

    async def _record_request(self):
        """Record a request timestamp."""
        async with self._lock:
            self.request_timestamps.append(time.time())
            self.total_requests += 1

    @asynccontextmanager
    async def acquire(self):
        """Acquire rate limiter slot (use as async context manager).
        
        Example:
            async with rate_limiter.acquire():
                response = await api_call()
        """
        # First, check rate limit before acquiring semaphore
        wait_time = await self._check_rate_limit()
        if wait_time:
            logger.warning(
                f"[{self.name}] Rate limit reached, waiting {wait_time:.1f}s "
                f"({len(self.request_timestamps)}/{self.requests_per_minute} rpm)"
            )
            self.total_waits += 1
            self.total_wait_time += wait_time
            await asyncio.sleep(wait_time)
        
        # Now acquire concurrency semaphore
        async with self.semaphore:
            await self._record_request()
            try:
                yield
            except Exception:
                raise

    def get_stats(self) -> dict:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "requests_per_minute": self.requests_per_minute,
            "current_requests_in_window": len(self.request_timestamps),
            "total_requests": self.total_requests,
            "total_waits": self.total_waits,
            "total_wait_time_seconds": round(self.total_wait_time, 2),
            "avg_wait_time": round(
                self.total_wait_time / self.total_waits, 2
            ) if self.total_waits > 0 else 0
        }

    def __repr__(self) -> str:
        return (
            f"RateLimiter(name={self.name}, "
            f"concurrent={self.max_concurrent}, rpm={self.requests_per_minute})"
        )


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on error responses.
    
    Automatically reduces rate when receiving 429 (Too Many Requests) errors.
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        requests_per_minute: int = 60,
        name: str = "AdaptiveRateLimiter",
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
        min_rpm: int = 5,
        max_rpm: int = 120
    ):
        """Initialize adaptive rate limiter.
        
        Args:
            max_concurrent: Maximum concurrent requests
            requests_per_minute: Starting requests per minute
            name: Name for logging
            backoff_factor: Multiply RPM by this on rate limit error (< 1)
            recovery_factor: Multiply RPM by this on success (> 1)
            min_rpm: Minimum RPM floor
            max_rpm: Maximum RPM ceiling
        """
        super().__init__(max_concurrent, requests_per_minute, name)
        
        self.base_rpm = requests_per_minute
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.min_rpm = min_rpm
        self.max_rpm = max_rpm
        
        self.rate_limit_errors = 0
        self.consecutive_successes = 0

    def report_error(self, is_rate_limit: bool = False):
        """Report an API error.
        
        Args:
            is_rate_limit: True if this was a 429/rate limit error
        """
        if is_rate_limit:
            self.rate_limit_errors += 1
            self.consecutive_successes = 0
            
            # Reduce RPM
            new_rpm = int(self.requests_per_minute * self.backoff_factor)
            new_rpm = max(self.min_rpm, new_rpm)
            
            if new_rpm != self.requests_per_minute:
                logger.warning(
                    f"[{self.name}] Rate limit hit, reducing RPM: "
                    f"{self.requests_per_minute} -> {new_rpm}"
                )
                self.requests_per_minute = new_rpm

    def report_success(self):
        """Report a successful API call."""
        self.consecutive_successes += 1
        
        # After 10 consecutive successes, try increasing rate
        if self.consecutive_successes >= 10:
            new_rpm = int(self.requests_per_minute * self.recovery_factor)
            new_rpm = min(self.max_rpm, new_rpm)
            
            if new_rpm != self.requests_per_minute:
                logger.info(
                    f"[{self.name}] Recovering RPM: "
                    f"{self.requests_per_minute} -> {new_rpm}"
                )
                self.requests_per_minute = new_rpm
                self.consecutive_successes = 0

    def get_stats(self) -> dict:
        """Get adaptive rate limiter statistics."""
        stats = super().get_stats()
        stats.update({
            "base_rpm": self.base_rpm,
            "current_rpm": self.requests_per_minute,
            "rate_limit_errors": self.rate_limit_errors,
            "consecutive_successes": self.consecutive_successes,
            "backoff_factor": self.backoff_factor,
        })
        return stats
