import type { DecodedGatewayMessage } from "./types.js";

export type ProtocolAdapter = {
  encodeAuth: (username: string, password: string) => Record<string, unknown>;
  encodeCommand: (
    name: string,
    args: Record<string, unknown>,
    id: string,
  ) => Record<string, unknown>;
  decodeMessage: (raw: string) => DecodedGatewayMessage;
};

export const defaultProtocolAdapter: ProtocolAdapter = {
  encodeAuth: (username, password) => ({
    type: "auth",
    username,
    password,
  }),
  encodeCommand: (name, args, id) => ({
    type: "command",
    id,
    name,
    args,
  }),
  decodeMessage: (raw) => {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      return {
        type: String(parsed.type ?? "unknown"),
        id: typeof parsed.id === "string" ? parsed.id : undefined,
        payload: (parsed.payload as Record<string, unknown>) ?? parsed,
      };
    } catch {
      return { type: "decode_error", payload: { raw } };
    }
  },
};
