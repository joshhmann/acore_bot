"""Base configuration class with shared utilities."""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional


class BaseConfig:
    """Base configuration class with common utilities."""

    @staticmethod
    def _get_env(key: str, default: Any = "") -> str:
        """Get string environment variable."""
        return os.getenv(key, default)

    @staticmethod
    def _get_env_bool(key: str, default: bool = False) -> bool:
        """Get boolean environment variable."""
        return os.getenv(key, str(default).lower()).lower() == "true"

    @staticmethod
    def _get_env_int(key: str, default: int = 0) -> int:
        """Get integer environment variable."""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _get_env_float(key: str, default: float = 0.0) -> float:
        """Get float environment variable."""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _get_env_list(
        key: str, default: Optional[List[str]] = None, delimiter: str = ","
    ) -> List[str]:
        """Get list environment variable."""
        if default is None:
            default = []
        value = os.getenv(key, "")
        if not value:
            return default
        return [x.strip() for x in value.split(delimiter) if x.strip()]

    @staticmethod
    def _get_env_int_list(key: str, default: Optional[List[int]] = None) -> List[int]:
        """Get list of integers from environment variable."""
        if default is None:
            default = []
        value = os.getenv(key, "")
        if not value:
            return default
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except ValueError:
            return default

    @staticmethod
    def _get_env_path(key: str, default: str = ".") -> Path:
        """Get path environment variable."""
        return Path(os.getenv(key, default))
