import { z } from "zod";

const summarySchemaWire = z.object({
  schema_type: z.string(),
  params: z.record(z.string(), z.unknown()),
});

const systemeConstructifWire = z.object({
  label: z.string(),
  description: z.string(),
  kpis: z.array(z.string()),
  details: z.array(z.string()),
  schema_: summarySchemaWire.nullish(),
});

const contrainteWire = z.object({
  label: z.string(),
  kpis: z.array(z.string()),
  details: z.array(z.string()),
});

const projectSummaryWire = z.object({
  description: z.string(),
  systeme_constructif: z.array(systemeConstructifWire),
  contraintes: z.array(contrainteWire),
});

/**
 * The summary stream contract, as `backend/app/services/summary.py` emits it.
 *
 * Validates the wire and does NOT transform it: `z.input` equals `z.output`.
 * Renaming a key here would give the mapping a second home, and two homes
 * diverge on the first backend change. Built once, never per event.
 */
export const summarySSEEvent = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("progress"),
    section: z.string(),
    index: z.number(),
    total: z.number(),
    status: z.enum(["done", "error", "skipped"]),
  }),
  z.object({
    type: z.literal("complete"),
    summary: projectSummaryWire,
    status: z.enum(["done", "partial", "error"]),
  }),
  z.object({
    type: z.literal("error"),
    message: z.string(),
  }),
]);

export type SummarySSEWire = z.infer<typeof summarySSEEvent>;
