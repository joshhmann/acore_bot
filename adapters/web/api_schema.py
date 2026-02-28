from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


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
