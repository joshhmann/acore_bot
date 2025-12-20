"""Production logging configuration with structured JSON output.

This module provides:
- Structured JSON logging for production environments
- Log rotation with size limits and compression
- Contextual logging helpers with trace IDs
- Backwards-compatible with existing text logging
"""

import logging
import logging.handlers
import json
import sys
import gzip
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timezone
from contextvars import ContextVar
import traceback

# Import Config for production settings
try:
    from config import Config
except ImportError:
    # Fallback if Config is not available (e.g., during testing)
    class Config:
        LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# Context variable for request/trace tracking
trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
context_data_ctx: ContextVar[Dict[str, Any]] = ContextVar("context_data", default={})


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_trace: bool = True):
        """Initialize JSON formatter.

        Args:
            include_trace: Include trace_id in output if available
        """
        super().__init__()
        self.include_trace = include_trace

    def _sanitize_exception_message(self, message: str) -> str:
        """Sanitize exception message to remove sensitive information.

        Removes:
        - File system paths (absolute and relative)
        - Environment variables
        - API keys/tokens (common patterns)
        - Database connection strings
        - Internal IP addresses

        Args:
            message: Raw exception message

        Returns:
            Sanitized message safe for production logging
        """
        import re

        if not message:
            return ""

        sanitized = message

        # Remove connection strings FIRST (before path matching interferes)
        sanitized = re.sub(
            r"(postgresql|mysql|mongodb|redis)://[^\s]+",
            r"\1://[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Remove potential API keys/tokens (common patterns)
        sanitized = re.sub(
            r"(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+",
            r"\1=[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )

        # Remove absolute file paths (Unix and Windows)
        sanitized = re.sub(r"(/[^\s]+/[^\s]+)", "[PATH]", sanitized)
        sanitized = re.sub(r"([A-Z]:\\[^\s]+)", "[PATH]", sanitized)

        # Remove environment variable patterns
        sanitized = re.sub(r"\$\{?[A-Z_][A-Z0-9_]*\}?", "[ENV_VAR]", sanitized)

        # Remove internal IP addresses (keep public IPs for debugging network issues)
        sanitized = re.sub(
            r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b",
            "[INTERNAL_IP]",
            sanitized,
        )

        # Limit message length to prevent log spam
        max_length = 500
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "... [truncated]"

        return sanitized

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of log record
        """
        # Build base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()
            + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add trace_id if available
        if self.include_trace:
            trace_id = trace_id_ctx.get()
            if trace_id:
                log_entry["trace_id"] = trace_id

        # Add context data if available
        context_data = context_data_ctx.get()
        if context_data:
            log_entry["context"] = context_data.copy()

        # Add extra fields from record - build context dict properly
        context_dict = (
            log_entry.get("context", {}).copy() if "context" in log_entry else {}
        )

        if hasattr(record, "user_id"):
            context_dict["user_id"] = getattr(record, "user_id")
        if hasattr(record, "channel_id"):
            context_dict["channel_id"] = getattr(record, "channel_id")
        if hasattr(record, "persona_id"):
            context_dict["persona_id"] = getattr(record, "persona_id")
        if hasattr(record, "guild_id"):
            context_dict["guild_id"] = getattr(record, "guild_id")
        if hasattr(record, "duration_ms"):
            context_dict["duration_ms"] = getattr(record, "duration_ms")

        # Only add context if we have any context data
        if context_dict:
            log_entry["context"] = context_dict

        # Add exception info if present (sanitized for production)
        if record.exc_info:
            is_debug_mode = Config.LOG_LEVEL == "DEBUG"

            if is_debug_mode:
                # DEBUG mode: Include full details for developers
                log_entry["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": traceback.format_exception(*record.exc_info),
                }
            else:
                # Production: Only safe, sanitized exception info
                exc_type = (
                    record.exc_info[0].__name__ if record.exc_info[0] else "Unknown"
                )
                exc_message = str(record.exc_info[1]) if record.exc_info[1] else ""

                # Sanitize message: Remove file paths and sensitive patterns
                sanitized_message = self._sanitize_exception_message(exc_message)

                log_entry["exception"] = {
                    "type": exc_type,
                    "message": sanitized_message,
                }

        # Add location info (sanitized in production)
        is_debug_mode = Config.LOG_LEVEL == "DEBUG"
        if is_debug_mode:
            # DEBUG: Full file paths for developers
            log_entry["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }
        else:
            # Production: Only relative filename, no full paths
            log_entry["location"] = {
                "file": record.filename,  # Just the filename, not full path
                "line": record.lineno,
                "function": record.funcName,
            }

        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter with enhanced context."""

    def __init__(self):
        """Initialize text formatter."""
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with context.

        Args:
            record: Log record to format

        Returns:
            Formatted text string
        """
        # Get base formatted message
        base_msg = super().format(record)

        # Add context information if available
        context_parts: List[str] = []

        # Add trace_id
        trace_id = trace_id_ctx.get()
        if trace_id:
            context_parts.append(f"trace_id={trace_id}")

        # Add extra context fields
        if hasattr(record, "user_id"):
            context_parts.append(f"user_id={getattr(record, 'user_id')}")
        if hasattr(record, "channel_id"):
            context_parts.append(f"channel_id={getattr(record, 'channel_id')}")
        if hasattr(record, "persona_id"):
            context_parts.append(f"persona_id={getattr(record, 'persona_id')}")
        if hasattr(record, "duration_ms"):
            context_parts.append(f"duration_ms={getattr(record, 'duration_ms')}")

        # Add context data
        context_data = context_data_ctx.get()
        if context_data:
            for key, value in context_data.items():
                context_parts.append(f"{key}={value}")

        if context_parts:
            base_msg += f" [{', '.join(context_parts)}]"

        return base_msg


class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that compresses old log files."""

    def doRollover(self):
        """Perform rollover and compress the old log file."""
        if self.stream:
            self.stream.close()

        # Rotate files
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename(f"{self.baseFilename}.{i}.gz")
                dfn = self.rotation_filename(f"{self.baseFilename}.{i + 1}.gz")
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)

            # Compress the current log file
            dfn = self.rotation_filename(f"{self.baseFilename}.1.gz")
            if os.path.exists(dfn):
                os.remove(dfn)

            # Compress using gzip
            with open(self.baseFilename, "rb") as f_in:
                with gzip.open(dfn, "wb") as f_out:
                    f_out.writelines(f_in)

            # Remove uncompressed file
            os.remove(self.baseFilename)

        # Open new log file
        if not self.delay:
            self.stream = self._open()


def log_with_context(
    logger: logging.Logger, level: int, message: str, **context: Any
) -> None:
    """Log a message with additional context.

    Args:
        logger: Logger instance to use
        level: Logging level (logging.INFO, logging.ERROR, etc.)
        message: Log message
        **context: Additional context fields (user_id, channel_id, etc.)
    """
    # Create log record with extra fields
    extra = {}
    for key, value in context.items():
        extra[key] = value

    logger.log(level, message, extra=extra)


class TraceContext:
    """Context manager for setting trace ID and context data."""

    def __init__(self, trace_id: str, **context: Any):
        """Initialize trace context.

        Args:
            trace_id: Unique trace identifier
            **context: Additional context fields
        """
        self.trace_id = trace_id
        self.context = context
        self.trace_token = None
        self.context_token = None

    def __enter__(self):
        """Enter context and set trace ID."""
        self.trace_token = trace_id_ctx.set(self.trace_id)
        self.context_token = context_data_ctx.set(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and reset trace ID."""
        if self.trace_token:
            trace_id_ctx.reset(self.trace_token)
        if self.context_token:
            context_data_ctx.reset(self.context_token)


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file_path: str = "logs/bot.log",
    log_format: str = "text",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    compress_old_logs: bool = True,
) -> logging.Logger:
    """Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Enable file logging
        log_file_path: Path to log file
        log_format: Output format ("json" or "text")
        max_bytes: Max file size before rotation
        backup_count: Number of backup files to keep
        compress_old_logs: Compress old log files with gzip

    Returns:
        Root logger instance
    """
    # Create logs directory
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Choose formatter based on format setting
    if log_format.lower() == "json":
        console_formatter = JSONFormatter()
        file_formatter = JSONFormatter()
    else:
        console_formatter = TextFormatter()
        file_formatter = TextFormatter()

    # Console handler (use requested format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (with rotation and optional compression)
    if log_to_file:
        if compress_old_logs:
            file_handler = CompressedRotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
            )
        else:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
            )

        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context.

    Returns:
        Current trace ID or None
    """
    return trace_id_ctx.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for current context.

    Args:
        trace_id: Trace ID to set
    """
    trace_id_ctx.set(trace_id)


def add_context_data(key: str, value: Any) -> None:
    """Add data to current context.

    Args:
        key: Context key
        value: Context value
    """
    context = context_data_ctx.get().copy()
    context[key] = value
    context_data_ctx.set(context)
