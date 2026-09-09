import { describe, expect, it } from "vitest";
import { chatSSEEvent } from "./chat.schema";

const source = {
  document_id: "d-1",
  filename: "cctp-lot-03.pdf",
  page: 12,
  lot: "03",
  phase: "PRO",
  text: "Dallage sur terre-plein, épaisseur 12 cm.",
};

const structured = {
  title: "Épaisseurs de dallage",
  columns: ["Ouvrage", "Épaisseur"],
  rows: [{ Ouvrage: "Dallage", Épaisseur: "12 cm" }],
};

const schema = {
  schema_type: "multicouche",
  title: "Coupe de dallage",
  params: { epaisseur: "0.12" },
};

describe("the chat stream contract", () => {
  it("accepts the conversation identifier event", () => {
    expect(chatSSEEvent.safeParse({ conversation_id: "c-9" }).success).toBe(true);
  });

  it("accepts a text fragment event", () => {
    expect(chatSSEEvent.safeParse({ text: "Le dallage " }).success).toBe(true);
  });

  it("accepts a structured table event", () => {
    expect(chatSSEEvent.safeParse({ structured }).success).toBe(true);
  });

  it("accepts a structured schema event", () => {
    expect(chatSSEEvent.safeParse({ schema }).success).toBe(true);
  });

  it("accepts a sources event", () => {
    expect(chatSSEEvent.safeParse({ sources: [source] }).success).toBe(true);
  });

  it("accepts an error event carrying a French message", () => {
    const result = chatSSEEvent.safeParse({
      error: "Le service de recherche est temporairement indisponible.",
    });

    expect(result.success).toBe(true);
  });

  it("accepts an event carrying two known keys at once", () => {
    const result = chatSSEEvent.safeParse({ text: "Réponse", sources: [source] });

    expect(result.success).toBe(true);
  });

  it("rejects an object carrying none of the keys the contract names", () => {
    const result = chatSSEEvent.safeParse({ jeton: "Le dallage " });

    expect(result.success).toBe(false);
  });

  it("rejects a text fragment that is not a string", () => {
    expect(chatSSEEvent.safeParse({ text: 42 }).success).toBe(false);
  });

  it("rejects a source list whose entries lost a field", () => {
    const incomplete: Record<string, unknown> = { ...source };
    delete incomplete.lot;

    expect(chatSSEEvent.safeParse({ sources: [incomplete] }).success).toBe(false);
  });
});
