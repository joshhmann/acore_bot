"""Rate limiting service for API calls."""
import asyncio
import time
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using a semaphore and time-based tracking.

    This implementation combines concurrency limiting (Semaphore)
    with rate limiting (requests per minute).
    """

    def __init__(self, max_concurrent: int = 5, requests_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            max_concurrent: Maximum concurrent requests allowed
            requests_per_minute: Maximum requests allowed per minute
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.requests = []  # List of timestamps
        self.rpm_limit = requests_per_minute
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self):
        """Acquire a slot for making a request.

        This context manager yields when a slot is available and rate limits are respected.

        Usage:
            async with rate_limiter.acquire():
                await make_api_call()
        """
        # First wait for concurrency slot
        async with self.semaphore:
            # Check rate limit in a loop to ensure we re-check after sleeping
            while True:
                wait_time = 0

                async with self._lock:
                    now = time.time()

                    # Filter out requests older than 1 minute
                    self.requests = [t for t in self.requests if now - t < 60]

                    if len(self.requests) < self.rpm_limit:
                        # Record this request and break loop
                        self.requests.append(now)
                        break
                    else:
                        # Calculate wait time
                        oldest_request = self.requests[0]
                        wait_time = 60 - (now - oldest_request)
                        if wait_time < 0:
                            wait_time = 0

                # Sleep outside the lock if we need to wait
                if wait_time > 0:
                    logger.warning(f"Rate limit reached ({self.rpm_limit}/min), waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                else:
                    # Should rarely happen if logic is correct, but safe guard
                    if len(self.requests) >= self.rpm_limit:
                         await asyncio.sleep(0.1)

            # Yield control to the caller
            try:
                yield
            finally:
                pass
