import { loadConfig } from "./config.js";
import { startMcpServer } from "./mcp/server.js";
import { GatewayClient } from "./rs/gateway_client.js";

const main = async (): Promise<void> => {
  const config = loadConfig();
  const gatewayClient = new GatewayClient(config);

  try {
    await gatewayClient.connect();
  } catch (err) {
    console.error("Initial gateway connection failed; background reconnect will continue", err);
  }

  await startMcpServer(config, gatewayClient);

  const shutdown = async () => {
    await gatewayClient.stop();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
};

void main();
