import crypto from "node:crypto";

import express from "express";

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

import type { BridgeConfig } from "../config.js";
import type { GatewayClient } from "../rs/gateway_client.js";
import { executeTool, toolSpecs } from "./tools.js";

const constantTimeEqual = (a: string, b: string): boolean => {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  if (aa.length !== bb.length) {
    return false;
  }
  return crypto.timingSafeEqual(aa, bb);
};

const createServer = (gateway: GatewayClient): Server => {
  const server = new Server(
    {
      name: "rs-mcp-bridge",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: toolSpecs().map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.input_schema,
    })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request: { params: { name: string; arguments?: unknown } }) => {
    const result = await executeTool(
      request.params.name,
      request.params.arguments ?? {},
      gateway,
    );

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      isError: !result.ok,
    };
  });

  return server;
};

const startHttpMcpServer = async (config: BridgeConfig, gateway: GatewayClient): Promise<void> => {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.use((req, res, next) => {
    if (!config.mcpApiKey) {
      next();
      return;
    }
    const provided = String(req.header("X-API-Key") ?? "");
    if (!provided || !constantTimeEqual(provided, config.mcpApiKey)) {
      res.status(401).json({
        ok: false,
        error: {
          code: "UNAUTHORIZED",
          message: "Invalid API key",
        },
      });
      return;
    }
    next();
  });

  const server = createServer(gateway);
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });
  await server.connect(transport);

  app.post(config.rsMcpHttpPath, async (req, res) => {
    await transport.handleRequest(req, res, req.body);
  });

  app.get(`${config.rsMcpHttpPath}/tools`, (_req, res) => {
    res.status(200).json({ tools: toolSpecs() });
  });

  app.post(`${config.rsMcpHttpPath}/tools/call`, async (req, res) => {
    const body = (req.body ?? {}) as { name?: string; arguments?: unknown };
    if (!body.name || typeof body.name !== "string") {
      res.status(200).json({
        ok: false,
        error: {
          code: "INVALID_REQUEST",
          message: "Missing tool name",
        },
      });
      return;
    }

    const result = await executeTool(body.name, body.arguments ?? {}, gateway);
    res.status(200).json(result);
  });

  app.get(config.rsMcpHttpPath, (_req, res) => {
    res.status(405).json({
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Method not allowed.",
      },
      id: null,
    });
  });

  app.get("/healthz", (_req, res) => {
    res.status(200).json({
      ok: true,
      service: "rs-mcp-bridge",
      gateway_connected: gateway.isConnected(),
      transport: "http",
    });
  });

  await new Promise<void>((resolve) => {
    app.listen(config.rsMcpHttpPort, config.rsMcpHttpHost, () => {
      console.log(`rs-mcp-bridge MCP HTTP listening on http://${config.rsMcpHttpHost}:${config.rsMcpHttpPort}${config.rsMcpHttpPath}`);
      resolve();
    });
  });
};

const startStdioMcpServer = async (gateway: GatewayClient): Promise<void> => {
  const server = createServer(gateway);
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("rs-mcp-bridge MCP stdio transport running");
};

export const startMcpServer = async (config: BridgeConfig, gateway: GatewayClient): Promise<void> => {
  if (config.rsMcpHttpEnabled) {
    await startHttpMcpServer(config, gateway);
    return;
  }

  await startStdioMcpServer(gateway);
};
