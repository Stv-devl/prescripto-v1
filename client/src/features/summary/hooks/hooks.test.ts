import { renderHook, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ok } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import * as summaryService from "../services/summary.service";
import type { ProjectSummaryData, SummarySSEEvent } from "../types/types";
import { useSummary, useSummaryGeneration } from "./hooks";

vi.mock("../services/summary.service");

/** Arms `streamSummary` with the domain events it should yield. */
function armStream(events: SummarySSEEvent[]): void {
  vi.mocked(summaryService.streamSummary).mockImplementation(async function* () {
    for (const event of events) yield event;
  });
}

const domainSummary: ProjectSummaryData = {
  description: "Bâtiment R+2 en zone urbaine",
  systemeConstructif: [
    {
      label: "Fondations",
      description: "Semelles filantes sur bon sol",
      kpis: ["Profondeur 0,80 m"],
      details: ["Béton C25/30"],
      schema: {
        schemaType: "semelle_filante",
        params: { fond_fouille: "0.80" },
      },
    },
  ],
  contraintes: [
    { label: "Mitoyenneté", kpis: ["2 murs"], details: ["Reprise en sous-oeuvre"] },
  ],
};

describe("useSummary", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("exposes the summary the service crossed into the domain", async () => {
    vi.mocked(summaryService.getSummary).mockResolvedValue(
      ok({
        id: "s-1",
        project_id: "p-1",
        status: "done",
        data: domainSummary,
        error_message: null,
        generated_at: "2026-09-01T00:00:00Z",
      }),
    );
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useSummary("p-1", true), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data).toEqual(domainSummary);
  });

  it("does not query while the caller says the summary does not exist", () => {
    const { wrapper } = createQueryClientWrapper();

    renderHook(() => useSummary("p-1", false), { wrapper });

    expect(summaryService.getSummary).not.toHaveBeenCalled();
  });
});

describe("useSummaryGeneration", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  async function generate(events: SummarySSEEvent[]) {
    armStream(events);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useSummaryGeneration("p-1"), { wrapper });

    await act(async () => {
      await result.current.generate();
    });

    return result;
  }

  it("exposes the progress events in the order the stream emits them", async () => {
    const result = await generate([
      { type: "progress", section: "Fondations", index: 1, total: 2, status: "done" },
      {
        type: "progress",
        section: "Contraintes",
        index: 2,
        total: 2,
        status: "skipped",
      },
    ]);

    expect(result.current.progress.map((p) => p.section)).toEqual([
      "Fondations",
      "Contraintes",
    ]);
    expect(result.current.progress.map((p) => p.status)).toEqual([
      "done",
      "skipped",
    ]);
  });

  it("exposes the summary the completed stream carried", async () => {
    const result = await generate([
      { type: "complete", summary: domainSummary, status: "done" },
    ]);

    expect(result.current.generatedData).toEqual(domainSummary);
    expect(result.current.finalStatus).toBe("done");
  });

  it("exposes the message when the stream carries an error event", async () => {
    const result = await generate([
      { type: "error", message: "Aucun document dans le projet" },
    ]);

    expect(result.current.error).toBe("Aucun document dans le projet");
  });

  it("stops announcing a generation in flight once the stream ends", async () => {
    const result = await generate([]);

    expect(result.current.isGenerating).toBe(false);
  });

  it("reports a French message and logs in English when the stream breaks its contract", async () => {
    vi.mocked(summaryService.streamSummary).mockImplementation(
      // eslint-disable-next-line require-yield
      async function* () {
        throw new Error("invalid_union: no matching discriminator");
      },
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useSummaryGeneration("p-1"), { wrapper });

    await act(async () => {
      await result.current.generate();
    });

    expect(result.current.error).toBe("Erreur lors de la génération du résumé.");
    expect(console.error).toHaveBeenCalledWith(
      "Summary generation failed:",
      expect.anything(),
    );
  });
});
