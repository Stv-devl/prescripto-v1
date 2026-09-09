import { describe, expect, it } from "vitest";
import { summarySSEEvent } from "./summary.schema";

/** The `complete` payload exactly as `summary.py:1132` emits it. */
const wireComplete = {
  type: "complete",
  summary: {
    description: "Bâtiment R+2 en zone urbaine",
    systeme_constructif: [
      {
        label: "Fondations",
        description: "Semelles filantes",
        kpis: ["Profondeur 0,80 m"],
        details: ["Béton C25/30"],
        schema_: {
          schema_type: "semelle_filante",
          params: { fond_fouille: "0.80" },
        },
      },
    ],
    contraintes: [{ label: "Mitoyenneté", kpis: [], details: [] }],
  },
  status: "done",
};

describe("the summary stream contract", () => {
  it("accepts a progress event as summary.py emits it", () => {
    const result = summarySSEEvent.safeParse({
      type: "progress",
      section: "Fondations",
      index: 1,
      total: 7,
      status: "done",
    });

    expect(result.success).toBe(true);
  });

  it("accepts a complete event carrying the schema_ key", () => {
    const result = summarySSEEvent.safeParse(wireComplete);

    expect(result.success).toBe(true);
  });

  it("accepts an error event carrying a French message", () => {
    const result = summarySSEEvent.safeParse({
      type: "error",
      message: "Aucun document dans le projet",
    });

    expect(result.success).toBe(true);
  });

  it("rejects a complete event whose summary key was renamed", () => {
    const { summary, ...rest } = wireComplete;

    const result = summarySSEEvent.safeParse({ ...rest, resume: summary });

    expect(result.success).toBe(false);
  });

  it("rejects a progress event whose status is outside the three the backend sends", () => {
    const result = summarySSEEvent.safeParse({
      type: "progress",
      section: "Fondations",
      index: 1,
      total: 7,
      status: "pending",
    });

    expect(result.success).toBe(false);
  });

  it("rejects an event whose type is not one the backend emits", () => {
    const result = summarySSEEvent.safeParse({ type: "heartbeat" });

    expect(result.success).toBe(false);
  });

  it("names the failing key in the issue it reports", () => {
    const renamed = {
      ...wireComplete,
      summary: {
        ...wireComplete.summary,
        systeme_constructif: [
          { ...wireComplete.summary.systeme_constructif[0], label: 42 },
        ],
      },
    };

    const result = summarySSEEvent.safeParse(renamed);

    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual([
      "summary",
      "systeme_constructif",
      0,
      "label",
    ]);
  });
});
