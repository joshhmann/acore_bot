import type { GatewayClient } from "../rs/gateway_client.js";
import {
  getStateInputSchema,
  healthInputSchema,
  interactInputSchema,
  jsonSchema,
  useItemInputSchema,
  walkToInputSchema,
} from "./schemas.js";

type ToolError = {
  code: string;
  message: string;
  details?: unknown;
};

export type ToolResult = {
  ok: boolean;
  [key: string]: unknown;
  error?: ToolError;
};

export type ToolSpec = {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
};

type ToolDef = {
  spec: ToolSpec;
  validate: (args: unknown) => { success: true; data: Record<string, unknown> } | { success: false; error: ToolError };
  run: (args: Record<string, unknown>, gateway: GatewayClient) => Promise<ToolResult>;
};

const parseArgs = (schema: { safeParse: (data: unknown) => { success: boolean; data?: unknown; error?: unknown } }, args: unknown) => {
  const parsed = schema.safeParse(args ?? {});
  if (!parsed.success) {
    return {
      success: false as const,
      error: {
        code: "INVALID_INPUT",
        message: "Tool input validation failed",
        details: parsed.error,
      },
    };
  }
  return { success: true as const, data: parsed.data as Record<string, unknown> };
};

const stableState = (username: string, raw: Record<string, unknown> | null): ToolResult => {
  const player = (raw?.player as Record<string, unknown>) ?? {};
  return {
    ok: true,
    ts: new Date().toISOString(),
    player: {
      username,
      x: player.x as number | undefined,
      y: player.y as number | undefined,
      plane: player.plane as number | undefined,
      hp: player.hp as number | undefined,
      prayer: player.prayer as number | undefined,
      run_energy: player.run_energy as number | undefined,
      animation: (player.animation as number | null | undefined) ?? null,
      in_combat: player.in_combat as boolean | undefined,
    },
    inventory: (raw?.inventory as Record<string, unknown>) ?? { items: [] },
    equipment: (raw?.equipment as Record<string, unknown>) ?? { items: [] },
    skills: (raw?.skills as Record<string, unknown>) ?? {},
    target: (raw?.target as Record<string, unknown>) ?? null,
    raw: raw ?? {},
  };
};

const normalizeError = (err: unknown): ToolResult => ({
  ok: false,
  error: {
    code: "GATEWAY_ERROR",
    message: err instanceof Error ? err.message : String(err),
  },
});

const defs: ToolDef[] = [
  {
    spec: {
      name: "health",
      description: "Check bridge and gateway health",
      input_schema: jsonSchema(healthInputSchema),
    },
    validate: (args) => parseArgs(healthInputSchema, args),
    run: async (_args, gateway) => ({
      ok: true,
      gateway_connected: gateway.isConnected(),
      bot_username: gateway.getBotUsername(),
      last_error: gateway.getLastError() || undefined,
    }),
  },
  {
    spec: {
      name: "get_state",
      description: "Get latest gameplay state snapshot",
      input_schema: jsonSchema(getStateInputSchema),
    },
    validate: (args) => parseArgs(getStateInputSchema, args),
    run: async (_args, gateway) => stableState(gateway.getBotUsername(), gateway.getLatestStateRaw()),
  },
  {
    spec: {
      name: "walk_to",
      description: "Request movement to coordinates",
      input_schema: jsonSchema(walkToInputSchema),
    },
    validate: (args) => parseArgs(walkToInputSchema, args),
    run: async (args, gateway) => {
      const botName = String(args.bot_name ?? "");
      if (!botName) {
        return {
          ok: false,
          error: {
            code: "INVALID_INPUT",
            message: "bot_name is required",
          },
        };
      }

      if (botName !== gateway.getBotUsername()) {
        return {
          ok: false,
          error: {
            code: "BOT_NOT_CONNECTED",
            message: `Requested bot '${botName}' is not connected in this bridge`,
            details: { configured_bot: gateway.getBotUsername() },
          },
        };
      }

      try {
        const raw = await gateway.sendCommand("walk_to", {
          x: args.x,
          y: args.y,
          plane: args.plane,
        });
        return {
          ok: true,
          result: String(raw.result ?? raw.message ?? "ok"),
          raw,
        };
      } catch (err) {
        return normalizeError(err);
      }
    },
  },
  {
    spec: {
      name: "interact",
      description: "Interact with game entities",
      input_schema: jsonSchema(interactInputSchema),
    },
    validate: (args) => parseArgs(interactInputSchema, args),
    run: async (args, gateway) => {
      try {
        const raw = await gateway.sendCommand("interact", args);
        return {
          ok: true,
          action: args.action,
          result: String(raw.result ?? raw.message ?? "ok"),
          raw,
        };
      } catch (err) {
        return normalizeError(err);
      }
    },
  },
  {
    spec: {
      name: "use_item",
      description: "Use an item, optionally on a target",
      input_schema: jsonSchema(useItemInputSchema),
    },
    validate: (args) => parseArgs(useItemInputSchema, args),
    run: async (args, gateway) => {
      try {
        const raw = await gateway.sendCommand("use_item", args);
        return {
          ok: true,
          result: String(raw.result ?? raw.message ?? "ok"),
          raw,
        };
      } catch (err) {
        return normalizeError(err);
      }
    },
  },
];

export const toolSpecs = (): ToolSpec[] => defs.map((d) => d.spec);

export const executeTool = async (
  name: string,
  args: unknown,
  gateway: GatewayClient,
): Promise<ToolResult> => {
  const def = defs.find((d) => d.spec.name === name);
  if (!def) {
    return {
      ok: false,
      error: {
        code: "TOOL_NOT_FOUND",
        message: `Unknown tool: ${name}`,
      },
    };
  }
  const validated = def.validate(args);
  if (!validated.success) {
    return { ok: false, error: validated.error };
  }
  try {
    return await def.run(validated.data, gateway);
  } catch (err) {
    return normalizeError(err);
  }
};
