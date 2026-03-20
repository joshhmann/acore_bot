import { describe, expect, it, vi } from "vitest";

import { loadConfig } from "../src/config.js";
import { GatewayClient, type GatewayTransport } from "../src/rs/gateway_client.js";

class FakeTransport implements GatewayTransport {
  public connected = false;
  public sent: string[] = [];
  public connectCalls = 0;
  public failConnect = false;
  private onMessage?: (raw: string) => void;
  private onClose?: () => void;
  private onError?: (err: Error) => void;

  async connect(
    _url: string,
    onMessage: (raw: string) => void,
    onClose: () => void,
    onError: (err: Error) => void,
  ): Promise<void> {
    this.connectCalls += 1;
    this.onMessage = onMessage;
    this.onClose = onClose;
    this.onError = onError;
    if (this.failConnect) {
      this.failConnect = false;
      throw new Error("connect failed");
    }
    this.connected = true;
  }

  async send(payload: string): Promise<void> {
    this.sent.push(payload);
  }

  async close(): Promise<void> {
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  emitMessage(payload: Record<string, unknown>): void {
    this.onMessage?.(JSON.stringify(payload));
  }

  emitClose(): void {
    this.connected = false;
    this.onClose?.();
  }

  emitError(err: Error): void {
    this.onError?.(err);
  }
}

const makeConfig = () => {
  process.env.RS_BOT_USERNAME = "bot";
  process.env.RS_BOT_PASSWORD = "pw";
  process.env.RS_GATEWAY_URL = "ws://localhost:7780";
  process.env.RS_REQUEST_TIMEOUT_MS = "50";
  process.env.RS_CONNECT_TIMEOUT_MS = "1000";
  process.env.RS_RECONNECT_BACKOFF_MS = "20..50";
  return loadConfig();
};

describe("GatewayClient", () => {
  it("handles successful command response with correlation id", async () => {
    const transport = new FakeTransport();
    const client = new GatewayClient(makeConfig(), undefined, () => transport);
    await client.connect();

    const p = client.sendCommand("walk_to", { x: 1, y: 2 });
    const commandMsg = JSON.parse(transport.sent[1] ?? "{}");
    transport.emitMessage({ type: "response", id: commandMsg.id, payload: { result: "ok" } });

    await expect(p).resolves.toEqual({ result: "ok" });
  });

  it("times out pending requests", async () => {
    const transport = new FakeTransport();
    const client = new GatewayClient(makeConfig(), undefined, () => transport);
    await client.connect();
    await expect(client.sendCommand("interact", { action: "Talk-to" })).rejects.toThrow(
      "timeout",
    );
  });

  it("updates latest state from push events", async () => {
    const transport = new FakeTransport();
    const client = new GatewayClient(makeConfig(), undefined, () => transport);
    await client.connect();

    transport.emitMessage({
      type: "state",
      payload: { player: { username: "bot", x: 3200, y: 3200 } },
    });
    expect(client.getLatestStateRaw()).toEqual({ player: { username: "bot", x: 3200, y: 3200 } });
  });

  it("reconnects after disconnect with backoff", async () => {
    vi.useFakeTimers();
    const first = new FakeTransport();
    const second = new FakeTransport();
    second.failConnect = true;
    const third = new FakeTransport();
    const transports = [first, second, third];
    const client = new GatewayClient(makeConfig(), undefined, () => transports.shift() ?? third);

    await client.connect();
    first.emitClose();

    await vi.runOnlyPendingTimersAsync();
    await vi.runOnlyPendingTimersAsync();

    expect(second.connectCalls).toBe(1);
    expect(third.connectCalls).toBe(1);
    vi.useRealTimers();
    await client.stop();
  });
});
