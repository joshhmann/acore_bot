# rs-mcp-bridge

Minimal MCP bridge that proxies gameplay control/state tools to an rs-sdk gateway over WebSocket.

This service is designed to be consumed by Gestalt as an MCP tool source.

## What this is

- MCP server exposing 5 tools (`health`, `get_state`, `walk_to`, `interact`, `use_item`)
- WebSocket client to an rs-sdk gateway
- Request/response correlation with per-request timeouts
- Auto reconnect with backoff + jitter
- Normalized tool errors (`{ ok:false, error:{ code, message, details? } }`)

## What this is not

- No vision/OCR/UI automation
- No game bot strategy logic
- No new Gestalt adapter

## Quick start

```bash
cp .env.example .env
npm install
npm run dev
```

Defaults:

- Stdio transport is the default mode
- HTTP transport is optional and disabled unless `RS_MCP_HTTP_ENABLED=true`
- HTTP defaults: host `0.0.0.0`, port `7007`, path `/mcp`

## Environment

Required/important:

- `RS_GATEWAY_URL` (e.g. `ws://localhost:7780` or `wss://your-host/gateway`)
- `RS_BOT_USERNAME`
- `RS_BOT_PASSWORD` (optional local)
- `RS_MCP_HTTP_ENABLED` (default `false`)
- `RS_MCP_HTTP_HOST` (default `0.0.0.0`)
- `RS_MCP_HTTP_PORT` (default `7007`)
- `RS_MCP_HTTP_PATH` (default `/mcp`)
- `MCP_API_KEY` (optional; if set require `X-API-Key` header)
- `RS_CONNECT_TIMEOUT_MS` (default `10000`)
- `RS_RECONNECT_BACKOFF_MS` range string (default `500..5000`)
- `RS_REQUEST_TIMEOUT_MS` (default `15000`)

## Running transports

Stdio MCP (default):

```bash
npm run dev
```

HTTP MCP:

```bash
RS_MCP_HTTP_ENABLED=true npm run dev
```

When HTTP mode is enabled, the MCP JSON-RPC endpoint is:

- `POST {RS_MCP_HTTP_PATH}`

and `GET` on the same path returns method-not-allowed per MCP expectations.

The REST helper endpoints from earlier versions are still available in HTTP mode:

- `GET {RS_MCP_HTTP_PATH}/tools`
- `POST {RS_MCP_HTTP_PATH}/tools/call`

## Tool list

1. `health({})`
2. `get_state({})`
3. `walk_to({ bot_name, x, y, plane? })`
4. `interact({ action, entity_id?, name?, x?, y? })`
5. `use_item({ action, item_name?, item_id?, target_name?, target_id? })`

## Example HTTP calls

List tools (HTTP helper):

```bash
curl -s http://localhost:7007/mcp/tools
```

Call tool (HTTP helper):

```bash
curl -s -X POST http://localhost:7007/mcp/tools/call \
  -H 'Content-Type: application/json' \
  -d '{"name":"health","arguments":{}}'
```

Call MCP JSON-RPC directly (streamable HTTP endpoint):

```bash
curl -s -X POST http://localhost:7007/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

With API key:

```bash
curl -s -X POST http://localhost:7007/mcp/tools/call \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-key' \
  -d '{"name":"get_state","arguments":{}}'
```

## Gestalt config example

```bash
GESTALT_MCP_ENABLED=true
GESTALT_MCP_SERVERS='[{"name":"rs","transport":"http","url":"https://YOUR_HOST/mcp","api_key":"optional"}]'
```

## Protocol adapter notes

Gateway message encoding/decoding is isolated in `src/rs/protocol.ts`.

- `encodeAuth(username, password)`
- `encodeCommand(name, args, id)`
- `decodeMessage(raw)`

If your rs-sdk gateway uses a different message shape, only adjust that file.

## Tests

```bash
npm test
```

Unit tests use mocked transports and do not require a real gateway.

## Docker

Build and run:

```bash
docker build -t rs-mcp-bridge .
docker run --env-file .env -p 7007:7007 rs-mcp-bridge
```

Or:

```bash
docker compose up --build -d
```
