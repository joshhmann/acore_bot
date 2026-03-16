"""Authentication module for Web Adapter.

Provides API key based authentication for the Gestalt web API.
Supports Bearer token and custom header authentication.
"""

from __future__ import annotations

import os
from typing import Optional

# FastAPI imports with fallback
try:
    from fastapi import HTTPException, Request, WebSocket
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    HTTPBearer = object  # type: ignore
    HTTPAuthorizationCredentials = object  # type: ignore
    Request = object  # type: ignore
    WebSocket = object  # type: ignore
    HTTPException = Exception  # type: ignore


class WebAuth:
    """API key authentication handler for web adapter.

    Supports multiple authentication methods:
    - Bearer token in Authorization header
    - Custom X-Gestalt-Token header
    - Environment-based API token configuration

    Example:
        auth = WebAuth()
        @app.get("/protected")
        async def protected(request: Request):
            auth.require_auth(request)
            return {"status": "ok"}
    """

    def __init__(self, api_token: Optional[str] = None):
        """Initialize authentication handler.

        Args:
            api_token: Optional API token. If not provided, reads from
                      GESTALT_API_TOKEN or ACORE_WEB_API_TOKEN env vars.
        """
        self._api_token = api_token or self._load_token_from_env()
        if FASTAPI_AVAILABLE:
            self._security = HTTPBearer(auto_error=False)
        else:
            self._security = None

    @staticmethod
    def _load_token_from_env() -> str:
        """Load API token from environment variables."""
        return str(
            os.environ.get("GESTALT_API_TOKEN")
            or os.environ.get("ACORE_WEB_API_TOKEN")
            or ""
        ).strip()

    @property
    def api_token(self) -> str:
        """Get the configured API token."""
        return self._api_token

    @property
    def is_enabled(self) -> bool:
        """Check if authentication is enabled (token is configured)."""
        return bool(self._api_token)

    def extract_bearer_token(self, auth_header: Optional[str]) -> str:
        """Extract bearer token from Authorization header.

        Args:
            auth_header: The Authorization header value.

        Returns:
            The extracted token or empty string if invalid.
        """
        if not auth_header:
            return ""
        value = auth_header.strip()
        if value.lower().startswith("bearer "):
            return value[7:].strip()
        return value

    def validate_token(self, token: str) -> bool:
        """Validate an API token.

        Args:
            token: The token to validate.

        Returns:
            True if token is valid or auth is disabled, False otherwise.
        """
        if not self.is_enabled:
            return True
        return bool(token) and token == self._api_token

    def require_auth(self, request: Request) -> None:
        """Require authentication for HTTP request.

        Args:
            request: The FastAPI request object.

        Raises:
            HTTPException: If authentication fails (401 Unauthorized).
        """
        if not FASTAPI_AVAILABLE:
            return

        if not self.is_enabled:
            return

        # Try Authorization header first
        auth_header = request.headers.get("authorization", "")
        token = self.extract_bearer_token(auth_header)

        # Fall back to X-Gestalt-Token header
        if not token:
            token = request.headers.get("x-gestalt-token", "").strip()

        if not self.validate_token(token):
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def require_auth_websocket(self, websocket: WebSocket) -> bool:
        """Require authentication for WebSocket connection.

        Args:
            websocket: The FastAPI WebSocket object.

        Returns:
            True if authentication succeeded.

        Raises:
            HTTPException: If authentication fails (via websocket.close).
        """
        if not FASTAPI_AVAILABLE:
            return True

        if not self.is_enabled:
            return True

        # Try to get token from subprotocols or query params
        token = ""

        # Check query parameters
        if hasattr(websocket, "query_params"):
            token = websocket.query_params.get("token", "")

        # Check headers
        if not token and hasattr(websocket, "headers"):
            auth_header = websocket.headers.get("authorization", "")
            token = self.extract_bearer_token(auth_header)

        if not token:
            await websocket.close(code=4401, reason="Authentication required")
            return False

        if not self.validate_token(token):
            await websocket.close(code=4401, reason="Invalid token")
            return False

        return True

    def get_auth_dependency(self):
        """Get FastAPI dependency for authentication.

        Returns:
            A dependency that validates authentication.
        """
        if not FASTAPI_AVAILABLE:
            return lambda: None

        async def auth_dependency(request: Request):
            self.require_auth(request)
            return True

        return auth_dependency


# Global auth instance (singleton pattern)
_global_auth: Optional[WebAuth] = None


def get_auth() -> WebAuth:
    """Get or create global auth instance."""
    global _global_auth
    if _global_auth is None:
        _global_auth = WebAuth()
    return _global_auth


def reset_auth() -> None:
    """Reset global auth instance (useful for testing)."""
    global _global_auth
    _global_auth = None


def extract_request_client_scope(request: Request | WebSocket | None) -> str:
    """Extract adapter client scope from request headers."""
    if request is None:
        return ""
    headers = getattr(request, "headers", {}) or {}
    return str(
        headers.get("x-gestalt-client-id")
        or headers.get("x-client-id")
        or ""
    ).strip()


def extract_request_user_id(request: Request | WebSocket | None) -> str:
    """Extract claimed user id from request headers."""
    if request is None:
        return ""
    headers = getattr(request, "headers", {}) or {}
    return str(headers.get("x-gestalt-user-id") or headers.get("x-user-id") or "").strip()


def resolve_request_actor_id(
    request: Request | WebSocket | None,
    *,
    auth: WebAuth,
    client_scope: str = "",
    platform: str = "web",
) -> str:
    """Resolve trusted actor id for runtime events."""
    claimed_user_id = extract_request_user_id(request)
    if not auth.is_enabled:
        return claimed_user_id or "web_user"
    scope = str(client_scope or "").strip()
    if scope:
        return f"authenticated:{platform}:{scope}"
    return f"authenticated:{platform}"
