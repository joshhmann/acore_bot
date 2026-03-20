import { describe, expect, it } from "vitest";

import { executeTool, toolSpecs } from "../src/mcp/tools.js";

const fakeGateway = {
  isConnected: () => true,
  getBotUsername: () => "bot",
  getLastError: () => "",
  getLatestStateRaw: () => ({ player: { x: 3200, y: 3200 } }),
  sendCommand: async (_name: string, _args: Record<string, unknown>) => ({ result: "ok" }),
};

describe("MCP tools", () => {
  it("advertises expected tool names and input schemas", () => {
    const specs = toolSpecs();
    expect(specs.map((t) => t.name)).toEqual([
      "health",
      "get_state",
      "walk_to",
      "interact",
      "use_item",
    ]);
    for (const spec of specs) {
      expect(spec.input_schema).toBeTruthy();
    }
  });

  it("validates tool inputs and normalizes validation errors", async () => {
    const result = await executeTool("walk_to", { bot_name: "bot", x: "bad" }, fakeGateway as never);
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("INVALID_INPUT");
  });

  it("returns normalized error for mismatched bot_name", async () => {
    const result = await executeTool("walk_to", { bot_name: "other", x: 3200, y: 3200 }, fakeGateway as never);
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("BOT_NOT_CONNECTED");
  });

  it("normalizes gateway errors", async () => {
    const gateway = {
      ...fakeGateway,
      sendCommand: async () => {
        throw new Error("gateway failed");
      },
    };
    const result = await executeTool("walk_to", { bot_name: "bot", x: 3200, y: 3200 }, gateway as never);
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("GATEWAY_ERROR");
  });

  it("normalizes unknown tool errors", async () => {
    const result = await executeTool("unknown", {}, fakeGateway as never);
    expect(result.ok).toBe(false);
    expect(result.error?.code).toBe("TOOL_NOT_FOUND");
  });

  it("returns stable get_state shape with missing fields", async () => {
    const gateway = {
      ...fakeGateway,
      getLatestStateRaw: () => ({ player: {} }),
    };
    const result = await executeTool("get_state", {}, gateway as never);
    expect(result.ok).toBe(true);
    expect(result.player).toBeTruthy();
    expect(result.inventory).toBeTruthy();
    expect(result.equipment).toBeTruthy();
    expect(result.skills).toBeTruthy();
  });
});
