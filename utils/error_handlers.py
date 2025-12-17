"""Reusable error handling decorators and utilities for production bot."""

import asyncio
import logging
import functools
import time
from typing import Optional, Callable, Any, Type
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Standard error types for categorization."""

    SERVICE_ERROR = "service_error"
    COMMAND_ERROR = "command_error"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


class ServiceError(Exception):
    """Base exception for service-level errors."""

    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.SERVICE_ERROR,
        user_message: Optional[str] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.user_message = user_message or self._get_default_user_message()

    def _get_default_user_message(self) -> str:
        """Get default user-friendly message."""
        return "Something went wrong. Please try again later."


class LLMServiceError(ServiceError):
    """Error from LLM service."""

    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            ErrorType.API_ERROR,
            user_message
            or "I'm having trouble thinking right now. Please try again in a moment.",
        )


class TTSServiceError(ServiceError):
    """Error from TTS service."""

    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            ErrorType.API_ERROR,
            user_message or "I can't speak right now, but I can still chat via text!",
        )


class RateLimitError(ServiceError):
    """Error when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        user_msg = "I'm getting a lot of requests right now. Please wait a moment and try again."
        if retry_after:
            user_msg = f"I'm getting a lot of requests. Please try again in {retry_after} seconds."
        super().__init__(message, ErrorType.RATE_LIMIT_ERROR, user_msg)
        self.retry_after = retry_after


class NetworkError(ServiceError):
    """Network connectivity error."""

    def __init__(self, message: str, user_message: Optional[str] = None):
        super().__init__(
            message,
            ErrorType.NETWORK_ERROR,
            user_message
            or "I'm having connection issues. Please try again in a moment.",
        )


def handle_service_error(
    error_type: ErrorType = ErrorType.SERVICE_ERROR,
    log_level: int = logging.ERROR,
    fallback_return: Any = None,
    track_metrics: bool = True,
):
    """Decorator for handling service-level errors with logging and user feedback.

    Args:
        error_type: Type of error for categorization
        log_level: Logging level for errors
        fallback_return: Value to return on error (None by default)
        track_metrics: Whether to track error in metrics

    Usage:
        @handle_service_error(error_type=ErrorType.API_ERROR)
        async def call_api():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ServiceError as e:
                # Already a ServiceError - log and re-raise
                logger.log(
                    log_level,
                    f"{func.__name__} failed: {e} (Type: {e.error_type.value})",
                )

                if track_metrics:
                    _track_error(e.error_type.value, str(e))

                raise
            except Exception as e:
                # Unexpected error - wrap and handle
                error_msg = f"{func.__name__} encountered unexpected error: {e}"
                logger.log(log_level, error_msg, exc_info=True)

                if track_metrics:
                    _track_error(error_type.value, error_msg)

                # Return fallback or raise wrapped error
                if fallback_return is not None:
                    return fallback_return

                raise ServiceError(error_msg, error_type) from e

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ServiceError as e:
                logger.log(
                    log_level,
                    f"{func.__name__} failed: {e} (Type: {e.error_type.value})",
                )

                if track_metrics:
                    _track_error(e.error_type.value, str(e))

                raise
            except Exception as e:
                error_msg = f"{func.__name__} encountered unexpected error: {e}"
                logger.log(log_level, error_msg, exc_info=True)

                if track_metrics:
                    _track_error(error_type.value, error_msg)

                if fallback_return is not None:
                    return fallback_return

                raise ServiceError(error_msg, error_type) from e

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def handle_command_error(
    user_message: str = "Command failed. Please try again.",
    log_level: int = logging.WARNING,
    track_metrics: bool = True,
):
    """Decorator for handling Discord command errors with user feedback.

    Args:
        user_message: Message to show to user on error
        log_level: Logging level for errors
        track_metrics: Whether to track error in metrics

    Usage:
        @handle_command_error(user_message="Failed to process your request.")
        async def my_command(ctx):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract context (first arg for commands)
            ctx = args[0] if args else None

            try:
                return await func(*args, **kwargs)
            except ServiceError as e:
                # Service error with user message
                logger.log(
                    log_level,
                    f"Command {func.__name__} failed: {e} (Type: {e.error_type.value})",
                )

                if track_metrics:
                    _track_error(ErrorType.COMMAND_ERROR.value, str(e))

                # Send user-friendly message
                if ctx and hasattr(ctx, "send"):
                    try:
                        await ctx.send(f"❌ {e.user_message}")
                    except Exception:
                        pass

                # Don't re-raise - command handled
                return None
            except Exception as e:
                # Unexpected error
                error_msg = f"Command {func.__name__} encountered unexpected error: {e}"
                logger.log(log_level, error_msg, exc_info=True)

                if track_metrics:
                    _track_error(ErrorType.COMMAND_ERROR.value, error_msg)

                # Send generic message to user
                if ctx and hasattr(ctx, "send"):
                    try:
                        await ctx.send(f"❌ {user_message}")
                    except Exception:
                        pass

                return None

        return wrapper

    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback called on each retry (func(attempt, delay, error))

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def unreliable_api_call():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt == max_retries:
                        break

                    # Calculate backoff delay
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            await on_retry(attempt + 1, delay, e)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # All retries exhausted
            if last_exception is not None:
                error_msg = f"{func.__name__} failed after {max_retries + 1} attempts: {last_exception}"
                logger.error(error_msg)
                raise last_exception
            else:
                error_msg = f"{func.__name__} failed after {max_retries + 1} attempts with no specific exception"
                logger.error(error_msg)
                raise Exception(error_msg)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        break

                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        try:
                            on_retry(attempt + 1, delay, e)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")

                    time.sleep(delay)

            if last_exception is not None:
                error_msg = f"{func.__name__} failed after {max_retries + 1} attempts: {last_exception}"
                logger.error(error_msg)
                raise last_exception
            else:
                error_msg = f"{func.__name__} failed after {max_retries + 1} attempts with no specific exception"
                logger.error(error_msg)
                raise Exception(error_msg)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _track_error(error_type: str, error_message: str):
    """Track error in metrics service if available.

    Args:
        error_type: Type of error
        error_message: Error message
    """
    try:
        # Try to get metrics service from global bot instance if available
        # This will work when the bot is initialized
        import sys

        # Look for bot instance in modules that might have it
        for module_name in ["main", "__main__"]:
            if module_name in sys.modules:
                module = sys.modules[module_name]
                if hasattr(module, "bot") and hasattr(module.bot, "services"):
                    metrics = module.bot.services.get("metrics")
                    if metrics:
                        metrics.record_error(error_type, error_message)
                        return

        # Alternative: try to get from config if metrics service is accessible
        # This is a fallback for when bot isn't fully initialized
        logger.debug(f"Metrics service not available for error tracking: {error_type}")

    except Exception as e:
        # Don't let metrics tracking break error handling
        logger.debug(f"Failed to track error in metrics: {e}")


class CircuitBreaker:
    """Circuit breaker pattern for failing services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            name: Name of the service
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            expected_exception: Exception type to catch
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    def call(self, func: Callable, *args, **kwargs):
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        # Check if we should attempt recovery
        if self.state == "OPEN":
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) >= self.recovery_timeout
            ):
                logger.info(
                    f"Circuit breaker {self.name}: Attempting recovery (HALF_OPEN)"
                )
                self.state = "HALF_OPEN"
            else:
                raise ServiceError(
                    f"Circuit breaker {self.name} is OPEN",
                    ErrorType.SERVICE_ERROR,
                    f"Service temporarily unavailable. Please try again later.",
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset circuit
            if self.state == "HALF_OPEN":
                logger.info(f"Circuit breaker {self.name}: Service recovered (CLOSED)")

            self.state = "CLOSED"
            self.failure_count = 0
            self.last_failure_time = None

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: Opening circuit after {self.failure_count} failures"
                )
                self.state = "OPEN"

            raise e

    async def call_async(self, func: Callable, *args, **kwargs):
        """Execute async function through circuit breaker."""
        if self.state == "OPEN":
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) >= self.recovery_timeout
            ):
                logger.info(
                    f"Circuit breaker {self.name}: Attempting recovery (HALF_OPEN)"
                )
                self.state = "HALF_OPEN"
            else:
                raise ServiceError(
                    f"Circuit breaker {self.name} is OPEN",
                    ErrorType.SERVICE_ERROR,
                    f"Service temporarily unavailable. Please try again later.",
                )

        try:
            result = await func(*args, **kwargs)

            if self.state == "HALF_OPEN":
                logger.info(f"Circuit breaker {self.name}: Service recovered (CLOSED)")

            self.state = "CLOSED"
            self.failure_count = 0
            self.last_failure_time = None

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: Opening circuit after {self.failure_count} failures"
                )
                self.state = "OPEN"

            raise e

    def reset(self):
        """Manually reset circuit breaker."""
        logger.info(f"Circuit breaker {self.name}: Manual reset")
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
