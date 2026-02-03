"""Analytics and dashboard configuration."""

from .base import BaseConfig


class AnalyticsConfig(BaseConfig):
    """Analytics and metrics configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("METRICS_ENABLED", True)
    SAVE_INTERVAL_MINUTES: int = BaseConfig._get_env_int(
        "METRICS_SAVE_INTERVAL_MINUTES", 60
    )
    RETENTION_DAYS: int = BaseConfig._get_env_int("METRICS_RETENTION_DAYS", 30)

    # WebSocket
    WEBSOCKET_UPDATE_INTERVAL: float = BaseConfig._get_env_float(
        "ANALYTICS_WEBSOCKET_UPDATE_INTERVAL", 2.0
    )

    # Error tracking
    ERROR_SPIKE_WINDOW_SECONDS: int = BaseConfig._get_env_int(
        "ERROR_SPIKE_WINDOW_SECONDS", 300
    )


class DashboardConfig(BaseConfig):
    """Dashboard configuration."""

    ENABLED: bool = BaseConfig._get_env_bool("ANALYTICS_DASHBOARD_ENABLED", False)
    PORT: int = BaseConfig._get_env_int("ANALYTICS_DASHBOARD_PORT", 8080)
    API_KEY: str = BaseConfig._get_env("ANALYTICS_API_KEY", "change_me_in_production")

    METRICS_ENABLED: bool = BaseConfig._get_env_bool("METRICS_ENABLED", True)
    METRICS_SAVE_INTERVAL_MINUTES: int = BaseConfig._get_env_int(
        "METRICS_SAVE_INTERVAL_MINUTES", 60
    )
    METRICS_RETENTION_DAYS: int = BaseConfig._get_env_int("METRICS_RETENTION_DAYS", 30)
    WEBSOCKET_UPDATE_INTERVAL: float = BaseConfig._get_env_float(
        "ANALYTICS_WEBSOCKET_UPDATE_INTERVAL", 2.0
    )
    ERROR_SPIKE_WINDOW_SECONDS: int = BaseConfig._get_env_int(
        "ERROR_SPIKE_WINDOW_SECONDS", 300
    )
