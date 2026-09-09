import { z } from "zod";

const source = z.object({
  document_id: z.string(),
  filename: z.string(),
  page: z.number(),
  lot: z.string(),
  phase: z.string(),
  text: z.string(),
});

const structuredTable = z.object({
  title: z.string(),
  columns: z.array(z.string()),
  rows: z.array(z.record(z.string(), z.string())),
});

const structuredSchema = z.object({
  schema_type: z.string(),
  title: z.string(),
  params: z.record(z.string(), z.string()),
});

const KNOWN_KEYS = [
  "conversation_id",
  "text",
  "structured",
  "schema",
  "sources",
  "error",
] as const;

/**
 * The chat stream contract, as `backend/app/services/chat/stream.py` emits it.
 *
 * Every key is optional because the backend sends one per event — but an object
 * carrying none of them is refused, which is the shape a renamed backend key
 * would take. Deliberately not a union of single-key objects: nothing forbids
 * grouping two keys later, and a union would forbid it forever.
 */
export const chatSSEEvent = z
  .object({
    conversation_id: z.string().optional(),
    text: z.string().optional(),
    structured: structuredTable.optional(),
    schema: structuredSchema.optional(),
    sources: z.array(source).optional(),
    error: z.string().optional(),
  })
  .refine(
    (event) => KNOWN_KEYS.some((key) => event[key] !== undefined),
    { message: "event carries none of the keys the chat contract names" },
  );

export type ChatSSEEvent = z.infer<typeof chatSSEEvent>;
