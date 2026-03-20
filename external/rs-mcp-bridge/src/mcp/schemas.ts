import { z } from "zod";

export const healthInputSchema = z.object({});
export const getStateInputSchema = z.object({});

export const walkToInputSchema = z.object({
  bot_name: z.string().min(1),
  x: z.number().int(),
  y: z.number().int(),
  plane: z.number().int().optional(),
});

export const interactInputSchema = z.object({
  action: z.string().min(1),
  entity_id: z.string().optional(),
  name: z.string().optional(),
  x: z.number().int().optional(),
  y: z.number().int().optional(),
});

export const useItemInputSchema = z.object({
  action: z.string().min(1),
  item_name: z.string().optional(),
  item_id: z.number().int().optional(),
  target_name: z.string().optional(),
  target_id: z.string().optional(),
});

export const jsonSchema = (schema: z.ZodTypeAny): Record<string, unknown> => {
  if (schema === healthInputSchema || schema === getStateInputSchema) {
    return { type: "object", properties: {}, required: [] };
  }
  if (schema === walkToInputSchema) {
    return {
      type: "object",
      properties: {
        bot_name: { type: "string" },
        x: { type: "number" },
        y: { type: "number" },
        plane: { type: "number" },
      },
      required: ["bot_name", "x", "y"],
    };
  }
  if (schema === interactInputSchema) {
    return {
      type: "object",
      properties: {
        action: { type: "string" },
        entity_id: { type: "string" },
        name: { type: "string" },
        x: { type: "number" },
        y: { type: "number" },
      },
      required: ["action"],
    };
  }
  return {
    type: "object",
    properties: {
      action: { type: "string" },
      item_name: { type: "string" },
      item_id: { type: "number" },
      target_name: { type: "string" },
      target_id: { type: "string" },
    },
    required: ["action"],
  };
};
