# Web/API Adapter Implementation Plan

## Vision

Create a FastAPI-based HTTP adapter that exposes the Acore framework via REST API and WebSocket. This enables:
- **n8n/Zapier Integration**: Webhook-based automation workflows
- **Custom Frontends**: React/Vue web interfaces
- **Simple Chat UI**: Built-in HTML chat interface for testing
- **API Access**: Programmatic access to all personas

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Adapter                              │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Server (Uvicorn)                                   │
│  ├── POST /chat          → Sync chat response               │
│  ├── POST /chat/async    → Async chat (webhook callback)    │
│  ├── WebSocket /ws       → Real-time chat stream            │
│  ├── GET  /personas      → List available personas          │
│  ├── GET  /health        → Health check                     │
│  └── GET  /              → Built-in chat UI (index.html)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Layer                               │
│  WebInputAdapter  →  EventBus  →  Core Services             │
│  WebOutputAdapter ←  EventBus  ←  Persona Responses         │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
adapters/web/
├── __init__.py           # Exports WebInputAdapter, WebOutputAdapter
├── adapter.py            # WebInputAdapter implementation
├── output.py             # WebOutputAdapter implementation
├── api_schema.py         # Pydantic models for API
├── routes.py             # FastAPI route definitions
├── websocket.py          # WebSocket handler
└── static/
    └── index.html        # Built-in chat UI
```

## API Schema

### Request Models

```python
# api_schema.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str
    persona_id: Optional[str] = "dagoth_ur"
    user_id: Optional[str] = "web_user"
    channel_id: Optional[str] = "web_channel"
    context: Optional[dict] = None

class ChatAsyncRequest(ChatRequest):
    webhook_url: str  # Callback URL for async response

class PersonaInfo(BaseModel):
    id: str
    display_name: str
    description: Optional[str]

class ChatResponse(BaseModel):
    response: str
    persona_id: str
    persona_name: str
    timestamp: datetime
    metadata: Optional[dict] = None

class HealthResponse(BaseModel):
    status: str
    personas_loaded: int
    uptime_seconds: float
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Synchronous chat (blocks until response) |
| POST | `/chat/async` | Async chat (returns immediately, POSTs to webhook) |
| WS | `/ws` | WebSocket for streaming chat |
| GET | `/personas` | List available personas |
| GET | `/health` | Health check endpoint |
| GET | `/` | Built-in chat UI |

## Tasks

### Phase 1: Core Implementation

- [ ] **Task 1: Create adapter package structure**
  - Create `adapters/web/__init__.py`
  - Create `adapters/web/api_schema.py` with Pydantic models
  - Verify: `python -c "from adapters.web.api_schema import ChatRequest"`

- [ ] **Task 2: Implement WebInputAdapter**
  - Create `adapters/web/adapter.py`
  - Implement `WebInputAdapter(InputAdapter)` with FastAPI app
  - Implement `start()` to launch Uvicorn server
  - Implement `stop()` for graceful shutdown
  - Implement `on_event()` callback registration
  - Verify: Adapter starts and listens on configured port

- [ ] **Task 3: Implement WebOutputAdapter**
  - Create `adapters/web/output.py`
  - Implement `WebOutputAdapter(OutputAdapter)`
  - Support synchronous response storage
  - Support webhook callbacks for async mode
  - Verify: Can send messages to waiting requests

- [ ] **Task 4: Implement API routes**
  - Create `adapters/web/routes.py`
  - Implement `POST /chat` (synchronous)
  - Implement `POST /chat/async` (webhook callback)
  - Implement `GET /personas`
  - Implement `GET /health`
  - Verify: `curl http://localhost:8000/health` returns 200

- [ ] **Task 5: Implement WebSocket handler**
  - Create `adapters/web/websocket.py`
  - Implement streaming chat via WebSocket
  - Handle connection lifecycle (connect, message, disconnect)
  - Verify: WebSocket client can send/receive messages

### Phase 2: Integration

- [ ] **Task 6: Update launcher.py**
  - Add `ACORE_WEB_ENABLED` environment variable support
  - Add `ACORE_WEB_PORT` (default: 8000)
  - Wire WebInputAdapter to EventBus
  - Wire WebOutputAdapter to EventBus
  - Verify: `ACORE_WEB_ENABLED=true python launcher.py` starts web server

- [ ] **Task 7: Create built-in chat UI**
  - Create `adapters/web/static/index.html`
  - Simple chat interface with persona selection
  - Uses `/chat` endpoint for messages
  - Verify: Open `http://localhost:8000/` in browser

### Phase 3: Testing & Documentation

- [ ] **Task 8: Add integration tests**
  - Create `tests/adapters/test_web_adapter.py`
  - Test synchronous chat endpoint
  - Test async chat with mock webhook
  - Test WebSocket connection
  - Verify: `pytest tests/adapters/test_web_adapter.py -v`

- [ ] **Task 9: Update documentation**
  - Add Web Adapter section to `docs/ARCHITECTURE.md`
  - Add API reference to `docs/API_REFERENCE.md`
  - Add usage examples to `README.md`
  - Verify: Docs render correctly

## Configuration

```env
# .env
ACORE_WEB_ENABLED=true
ACORE_WEB_PORT=8000
ACORE_WEB_HOST=0.0.0.0
ACORE_WEB_API_KEY=your_api_key_here  # Optional auth
```

## Usage Examples

### Synchronous Chat
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "persona_id": "dagoth_ur"}'
```

### Async Chat (Webhook)
```bash
curl -X POST http://localhost:8000/chat/async \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello!",
    "persona_id": "dagoth_ur",
    "webhook_url": "https://your-n8n-instance.com/webhook/response"
  }'
```

### WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => ws.send(JSON.stringify({
  message: "Hello!",
  persona_id: "dagoth_ur"
}));
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

### n8n Integration
```
[HTTP Request] → POST /chat → [Response] → [Your Workflow]
```

## Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "websockets>=12.0",
]
```

## Verification Checklist

After all tasks complete:
- [ ] `ACORE_WEB_ENABLED=true python launcher.py` starts without errors
- [ ] `curl http://localhost:8000/health` returns `{"status": "healthy"}`
- [ ] `curl -X POST http://localhost:8000/chat -d '{"message":"hi"}'` returns response
- [ ] WebSocket connection works in browser console
- [ ] Built-in UI at `http://localhost:8000/` is functional
- [ ] All tests pass: `pytest tests/adapters/test_web_adapter.py -v`

## Estimated Effort

- Phase 1: ~2-3 hours
- Phase 2: ~1 hour
- Phase 3: ~1-2 hours
- **Total**: ~4-6 hours

## Notes

- Consider rate limiting for production use
- API key authentication is optional but recommended for public deployments
- WebSocket connections should handle reconnection gracefully
- Consider SSE (Server-Sent Events) as alternative to WebSocket for simpler clients
