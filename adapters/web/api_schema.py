from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message text")
    persona_id: Optional[str] = Field(
        default="dagoth_ur", description="Persona to use for response"
    )
    user_id: Optional[str] = Field(
        default="web_user", description="Unique user identifier"
    )
    channel_id: Optional[str] = Field(
        default="web_channel", description="Channel/conversation ID"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context data"
    )


class ChatAsyncRequest(ChatRequest):
    webhook_url: str = Field(..., description="Callback URL for async response")


class PersonaInfo(BaseModel):
    id: str = Field(..., description="Persona identifier")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(default=None, description="Persona description")
    avatar_url: Optional[str] = Field(default=None, description="Avatar image URL")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Persona response text")
    persona_id: str = Field(..., description="ID of responding persona")
    persona_name: str = Field(..., description="Display name of persona")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Service status")
    personas_loaded: int = Field(default=0, description="Number of loaded personas")
    uptime_seconds: float = Field(default=0.0, description="Service uptime")
    version: str = Field(default="1.0.0", description="API version")


class RuntimeContextRequest(BaseModel):
    session_id: str = Field(default="web:main", description="Runtime session id")
    persona_id: str = Field(default="", description="Persona id")
    mode: str = Field(default="", description="Optional mode override")
    room_id: str = Field(default="web_room", description="Room id")
    platform: str = Field(default="web", description="Adapter/platform name")
    flags: Dict[str, Any] = Field(default_factory=dict, description="Runtime flags")
    user_id: str = Field(default="", description="Optional user override")


class RuntimeEventRequest(RuntimeContextRequest):
    text: str = Field(..., description="Chat or command text")
    kind: str = Field(default="chat", description="Event kind: chat or command")
    message_id: str = Field(default="", description="Optional message identifier")


class RuntimeListSessionsRequest(BaseModel):
    limit: int = Field(default=20, description="Max sessions to return")
    platform: str = Field(default="", description="Filter by platform")
    room_id: str = Field(default="", description="Filter by room id")
    user_scope: str = Field(default="", description="Filter by user scope")


class RuntimeSocialModeRequest(RuntimeContextRequest):
    social_mode: str = Field(..., description="Social mode override")


class RuntimeTraceRequest(BaseModel):
    session_id: str = Field(default="web:main", description="Runtime session id")
    limit: int = Field(default=10, description="Trace span limit")
