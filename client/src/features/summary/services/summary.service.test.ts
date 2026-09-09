import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, fetchSSE } from "@/lib/apiClient";
import { HttpError } from "@/lib/errors";
import { ok } from "@/lib/result";
import {
  generateSummarySSE,
  getSummary,
  getSummaryStatus,
  streamSummary,
} from "./summary.service";

vi.mock("@/lib/apiClient");

/** A Response whose body streams the given SSE payloads. */
function sseResponse(lines: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(`data: ${line}\n\n`));
      }
      controller.close();
    },
  });

  return new Response(stream, { status: 200 });
}

const wireSummary = {
  description: "Groupe scolaire de 12 classes.",
  systeme_constructif: [
    {
      label: "Infrastructure",
      description: "Fondations superficielles filantes.",
      kpis: ["Semelles filantes 50×20 cm"],
      details: ["Béton C25/30 XC2"],
      schema_: {
        schema_type: "semelle_filante",
        params: { largeur_cm: "50" },
      },
    },
  ],
  contraintes: [],
};

const domainSummary = {
  description: "Groupe scolaire de 12 classes.",
  systemeConstructif: [
    {
      label: "Infrastructure",
      description: "Fondations superficielles filantes.",
      kpis: ["Semelles filantes 50×20 cm"],
      details: ["Béton C25/30 XC2"],
      schema: { schemaType: "semelle_filante", params: { largeur_cm: "50" } },
    },
  ],
  contraintes: [],
};

describe("summary.service", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the status the transport sent back", async () => {
    const status = {
      has_documents: true,
      has_summary: false,
      status: null,
    };
    vi.mocked(apiGet).mockResolvedValue(status);

    await expect(getSummaryStatus("p-1")).resolves.toEqual(ok(status));
  });

  it("returns the summary the transport sent back", async () => {
    const summary = {
      id: "s-1",
      project_id: "p-1",
      status: "done",
      data: null,
      error_message: null,
      generated_at: "2026-09-01T00:00:00Z",
    };
    vi.mocked(apiGet).mockResolvedValue(summary);

    await expect(getSummary("p-1")).resolves.toEqual(ok(summary));
  });

  it("builds each path from the project identifier", async () => {
    vi.mocked(apiGet).mockResolvedValue({});
    vi.mocked(fetchSSE).mockResolvedValue(new Response(null));

    await getSummaryStatus("p-42");
    await getSummary("p-42");
    await generateSummarySSE("p-42");

    expect(apiGet).toHaveBeenNthCalledWith(1, "/projects/p-42/summary/status");
    expect(apiGet).toHaveBeenNthCalledWith(2, "/projects/p-42/summary");
    expect(fetchSSE).toHaveBeenCalledWith(
      "/projects/p-42/summary/generate",
      {},
    );
  });

  it("hands back the streaming Response without consuming it", async () => {
    const response = new Response("data: chunk\n\n");
    vi.mocked(fetchSSE).mockResolvedValue(response);

    const result = await generateSummarySSE("p-1");

    expect(result).toBe(response);
    expect(result.bodyUsed).toBe(false);
  });

  it("hands back the Response even when it carries an error status", async () => {
    const response = new Response("boom", { status: 500 });
    vi.mocked(fetchSSE).mockResolvedValue(response);

    const result = await generateSummarySSE("p-1");

    expect(result.status).toBe(500);
  });

  it("surfaces a missing summary as a failed result carrying its code", async () => {
    vi.mocked(apiGet).mockRejectedValue(
      new HttpError(404, "No summary found for this project"),
    );

    await expect(getSummary("p-1")).resolves.toMatchObject({
      success: false,
      error: { code: "not_found" },
    });
  });

  it("returns the cached summary crossed into the domain", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      id: "s-1",
      project_id: "p-1",
      status: "done",
      data: wireSummary,
      error_message: null,
      generated_at: "2026-09-01T00:00:00Z",
    });

    const result = await getSummary("p-1");

    expect(result.success && result.data.data).toEqual(domainSummary);
  });

  it("leaves the summary payload null when the project has none", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      id: "s-1",
      project_id: "p-1",
      status: "generating",
      data: null,
      error_message: null,
      generated_at: null,
    });

    const result = await getSummary("p-1");

    expect(result.success && result.data.data).toBeNull();
  });

  it("does not throw when the transport omits the summary payload entirely", async () => {
    vi.mocked(apiGet).mockResolvedValue({ id: "s-1", project_id: "p-1" });

    await expect(getSummary("p-1")).resolves.toMatchObject({ success: true });
  });

  it("streams the events in the order the backend emits them", async () => {
    vi.mocked(fetchSSE).mockResolvedValue(
      sseResponse([
        '{"type":"progress","section":"Infrastructure","index":1,"total":2,"status":"done"}',
        '{"type":"progress","section":"Contraintes","index":2,"total":2,"status":"skipped"}',
        "[DONE]",
      ]),
    );

    const seen: string[] = [];
    for await (const event of streamSummary("p-1")) {
      if (event.type === "progress") seen.push(event.section);
    }

    expect(seen).toEqual(["Infrastructure", "Contraintes"]);
  });

  it("crosses the completed summary into the domain as it streams it", async () => {
    vi.mocked(fetchSSE).mockResolvedValue(
      sseResponse([
        `{"type":"complete","summary":${JSON.stringify(wireSummary)},"status":"done"}`,
        "[DONE]",
      ]),
    );

    const events = [];
    for await (const event of streamSummary("p-1")) events.push(event);

    expect(events).toEqual([
      { type: "complete", summary: domainSummary, status: "done" },
    ]);
  });

  it("fails visibly when the stream carries an event outside the contract", async () => {
    vi.mocked(fetchSSE).mockResolvedValue(
      sseResponse(['{"type":"progress","section":"Infrastructure"}', "[DONE]"]),
    );

    await expect(
      (async () => {
        for await (const event of streamSummary("p-1")) void event;
      })(),
    ).rejects.toThrow();
  });
});
