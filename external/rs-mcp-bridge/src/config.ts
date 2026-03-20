import dotenv from "dotenv";

dotenv.config();

const toInt = (value: string | undefined, fallback: number): number => {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const toRange = (value: string | undefined, fallback: [number, number]): [number, number] => {
  const [a, b] = (value ?? "").split("..");
  const min = Number.parseInt(a ?? "", 10);
  const max = Number.parseInt(b ?? "", 10);
  if (Number.isFinite(min) && Number.isFinite(max) && min <= max) {
    return [min, max];
  }
  return fallback;
};

export type BridgeConfig = {
  rsGatewayUrl: string;
  rsBotUsername: string;
  rsBotPassword: string;
  rsServer?: string;
  rsMcpHttpEnabled: boolean;
  rsMcpHttpHost: string;
  rsMcpHttpPort: number;
  rsMcpHttpPath: string;
  mcpApiKey?: string;
  rsConnectTimeoutMs: number;
  rsReconnectBackoffMs: [number, number];
  rsRequestTimeoutMs: number;
};

export const loadConfig = (): BridgeConfig => {
  const httpPathRaw = process.env.RS_MCP_HTTP_PATH ?? process.env.MCP_BASE_PATH ?? "/mcp";
  const rsMcpHttpPath = httpPathRaw.startsWith("/") ? httpPathRaw : `/${httpPathRaw}`;

  return {
    rsGatewayUrl: process.env.RS_GATEWAY_URL ?? "ws://localhost:7780",
    rsBotUsername: process.env.RS_BOT_USERNAME ?? "",
    rsBotPassword: process.env.RS_BOT_PASSWORD ?? "",
    rsServer: process.env.RS_SERVER,
    rsMcpHttpEnabled: (process.env.RS_MCP_HTTP_ENABLED ?? "false").toLowerCase() === "true",
    rsMcpHttpHost: process.env.RS_MCP_HTTP_HOST ?? "0.0.0.0",
    rsMcpHttpPort: toInt(process.env.RS_MCP_HTTP_PORT ?? process.env.MCP_HTTP_PORT ?? process.env.PORT, 7007),
    rsMcpHttpPath,
    mcpApiKey: process.env.MCP_API_KEY,
    rsConnectTimeoutMs: toInt(process.env.RS_CONNECT_TIMEOUT_MS, 10000),
    rsReconnectBackoffMs: toRange(process.env.RS_RECONNECT_BACKOFF_MS, [500, 5000]),
    rsRequestTimeoutMs: toInt(process.env.RS_REQUEST_TIMEOUT_MS, 15000),
  };
};
