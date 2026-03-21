# Web adapter package initialization

"""Web adapter for Gestalt Framework.

This package provides HTTP and WebSocket adapters for the Gestalt runtime,
following the Adapter SDK Contract (v1.0) with four-phase lifecycle:
- parse: Extract PlatformFacts from web request
- to_runtime_event: Build runtime Event using shared helper
- from_runtime_response: Extract RuntimeDecision from Response
- render: Return JSON response for web transport
"""

from adapters.web.adapter import WebAdapter, WebInputAdapter, WebOutputAdapter

__all__ = [
    "WebAdapter",
    "WebInputAdapter",
    "WebOutputAdapter",
]
