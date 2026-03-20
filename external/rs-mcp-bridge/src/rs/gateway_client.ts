import { randomUUID } from "node:crypto";
import WebSocket from "ws";

import type { BridgeConfig } from "../config.js";
import { defaultProtocolAdapter, type ProtocolAdapter } from "./protocol.js";
import type { DecodedGatewayMessage, GatewayStateSnapshot, PendingRequest } from "./types.js";

export type GatewayTransport = {
  connect: (url: string, onMessage: (raw: string) => void, onClose: () => void, onError: (err: Error) => void) => Promise<void>;
  send: (payload: string) => Promise<void>;
  close: () => Promise<void>;
  isConnected: () => boolean;
};

export class WsGatewayTransport implements GatewayTransport {
  private socket: WebSocket | null = null;

  async connect(
    url: string,
    onMessage: (raw: string) => void,
    onClose: () => void,
    onError: (err: Error) => void,
  ): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(url);
      this.socket = socket;
      socket.on("open", () => resolve());
      socket.on("message", (data) => onMessage(String(data)));
      socket.on("close", () => onClose());
      socket.on("error", (err) => {
        onError(err instanceof Error ? err : new Error(String(err)));
        reject(err);
      });
    });
  }

  async send(payload: string): Promise<void> {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("Gateway socket is not connected");
    }
    this.socket.send(payload);
  }

  async close(): Promise<void> {
    if (!this.socket) {
      return;
    }
    this.socket.close();
    this.socket = null;
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

export class GatewayClient {
  private readonly config: BridgeConfig;
  private readonly protocol: ProtocolAdapter;
  private readonly transportFactory: () => GatewayTransport;
  private transport: GatewayTransport;
  private pending = new Map<string, PendingRequest>();
  private latestState: GatewayStateSnapshot | null = null;
  private lastError = "";
  private reconnectDelayMs: number;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private shouldReconnect = true;

  constructor(
    config: BridgeConfig,
    protocol: ProtocolAdapter = defaultProtocolAdapter,
    transportFactory: () => GatewayTransport = () => new WsGatewayTransport(),
  ) {
    this.config = config;
    this.protocol = protocol;
    this.transportFactory = transportFactory;
    this.transport = this.transportFactory();
    this.reconnectDelayMs = this.config.rsReconnectBackoffMs[0];
  }

  async connect(): Promise<void> {
    this.shouldReconnect = true;
    await this.openConnection();
  }

  async stop(): Promise<void> {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    await this.transport.close();
    this.rejectAllPending("Gateway client stopped");
  }

  isConnected(): boolean {
    return this.transport.isConnected();
  }

  getLastError(): string {
    return this.lastError;
  }

  getLatestState(): GatewayStateSnapshot | null {
    return this.latestState;
  }

  getLatestStateRaw(): Record<string, unknown> | null {
    return (this.latestState?.raw as Record<string, unknown>) ?? null;
  }

  getBotUsername(): string {
    return this.config.rsBotUsername;
  }

  async sendCommand(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (!this.isConnected()) {
      throw new Error("Gateway is disconnected");
    }
    const id = randomUUID();
    const wire = this.protocol.encodeCommand(name, args, id);

    const responsePromise = new Promise<Record<string, unknown>>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Gateway request timeout for command '${name}'`));
      }, this.config.rsRequestTimeoutMs);
      this.pending.set(id, { resolve, reject, timer });
    });

    await this.transport.send(JSON.stringify(wire));
    return responsePromise;
  }

  private async openConnection(): Promise<void> {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error("Gateway connect timeout")), this.config.rsConnectTimeoutMs);
    });

    const connectPromise = this.transport.connect(
      this.config.rsGatewayUrl,
      (raw) => this.onMessage(raw),
      () => this.onClose(),
      (err) => this.onError(err),
    );

    await Promise.race([connectPromise, timeoutPromise]);
    this.reconnectDelayMs = this.config.rsReconnectBackoffMs[0];
    const authMessage = this.protocol.encodeAuth(this.config.rsBotUsername, this.config.rsBotPassword);
    await this.transport.send(JSON.stringify(authMessage));
  }

  private onMessage(raw: string): void {
    const decoded = this.protocol.decodeMessage(raw);
    this.handleDecoded(decoded);
  }

  private handleDecoded(decoded: DecodedGatewayMessage): void {
    if (decoded.type === "state") {
      this.latestState = {
        ...(decoded.payload as GatewayStateSnapshot),
        raw: decoded.payload ?? {},
      };
      return;
    }

    if (decoded.id && this.pending.has(decoded.id)) {
      const pending = this.pending.get(decoded.id);
      if (!pending) {
        return;
      }
      clearTimeout(pending.timer);
      this.pending.delete(decoded.id);

      if (decoded.type === "error") {
        pending.reject(new Error(String(decoded.payload?.message ?? "Gateway command error")));
        return;
      }
      pending.resolve((decoded.payload as Record<string, unknown>) ?? {});
    }
  }

  private onClose(): void {
    this.rejectAllPending("Gateway disconnected");
    if (this.shouldReconnect) {
      this.scheduleReconnect();
    }
  }

  private onError(err: Error): void {
    this.lastError = err.message;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || !this.shouldReconnect) {
      return;
    }
    const [minDelay, maxDelay] = this.config.rsReconnectBackoffMs;
    const jitter = Math.floor(Math.random() * 150);
    const waitMs = Math.min(maxDelay, this.reconnectDelayMs + jitter);
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      this.transport = this.transportFactory();
      try {
        await this.openConnection();
      } catch (err) {
        this.lastError = err instanceof Error ? err.message : String(err);
        this.reconnectDelayMs = Math.min(maxDelay, Math.max(minDelay, this.reconnectDelayMs * 2));
        this.scheduleReconnect();
      }
    }, waitMs);
  }

  private rejectAllPending(message: string): void {
    for (const [id, pending] of this.pending.entries()) {
      clearTimeout(pending.timer);
      pending.reject(new Error(message));
      this.pending.delete(id);
    }
  }
}
