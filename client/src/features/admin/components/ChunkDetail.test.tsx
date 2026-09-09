import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { chunkDetail, similarChunks } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { ChunkDetail } from "./ChunkDetail";

vi.mock("../services/admin.service");

const NOT_FOUND_COPY = "Chunk introuvable.";
const SERVER_COPY = "Le service est momentanément indisponible. Réessayez.";

/** Without a selected chunk the panel stays closed and the query is disabled. */
function renderWithSelectedChunk() {
  useAdminStore.getState().selectChunk("chunk-1");
  return renderWithProviders(<ChunkDetail projectId="p-1" />);
}

/** Opens the editor and puts the caret inside the text, as `handleSplit` requires. */
async function openEditorWithCaret(): Promise<void> {
  await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
  const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
  textarea.setSelectionRange(10, 10);
}

describe("ChunkDetail — the panel says what failed and never fakes a success", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(ok([]));
  });

  it("renders the failure instead of « Chunk introuvable. » when loading the chunk failed", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(
      err({ code: "server_error", message: "chunk detail failed" }),
    );
    renderWithSelectedChunk();

    expect(await screen.findByRole("alert")).toHaveTextContent(SERVER_COPY);
    expect(screen.queryByText(NOT_FOUND_COPY)).not.toBeInTheDocument();
  });

  it("renders « Chunk introuvable. » when the chunk genuinely does not exist", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(
      ok(null as unknown as typeof chunkDetail),
    );
    renderWithSelectedChunk();

    expect(await screen.findByText(NOT_FOUND_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says the refresh failed while keeping the chunk on screen, instead of showing stale text in silence", async () => {
    vi.mocked(adminService.getChunkDetail)
      .mockResolvedValueOnce(ok(chunkDetail))
      .mockResolvedValue(err({ code: "server_error", message: "refetch failed" }));
    const { queryClient } = renderWithSelectedChunk();

    await screen.findByText(chunkDetail.text);
    await queryClient.invalidateQueries();

    expect(await screen.findByRole("alert")).toHaveTextContent(SERVER_COPY);
    expect(screen.getByText(chunkDetail.text)).toBeInTheDocument();
  });

  it("shows a failed deletion inside the panel, without closing the chunk detail", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.deleteChunk).mockResolvedValue(
      err({ code: "conflict", message: "delete rejected" }),
    );
    renderWithSelectedChunk();

    await userEvent.click(
      await screen.findByRole("button", { name: "Supprimer le chunk" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cette donnée existe déjà",
    );
    expect(screen.getByText(chunkDetail.text)).toBeInTheDocument();
  });

  it("shows a failed split and leaves the chunk as it was, with no success state", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.splitChunk).mockResolvedValue(
      err({ code: "validation_failed", message: "split rejected" }),
    );
    renderWithSelectedChunk();

    await openEditorWithCaret();
    await userEvent.click(screen.getByRole("button", { name: /Scinder/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Certaines informations sont invalides",
    );
    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-1");
  });

  it("shows a failed merge next to the merge button, not off-screen at the top of the panel", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.mergeChunks).mockResolvedValue(
      err({ code: "conflict", message: "merge rejected" }),
    );
    renderWithSelectedChunk();

    await userEvent.click(await screen.findByRole("button", { name: /Fusionner/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Cette donnée existe déjà");
    expect(
      screen.getByRole("button", { name: /Fusionner/ }).closest("section"),
    ).toContainElement(alert);
  });

  it("clears the previous action's failure when a new action is started", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.deleteChunk).mockResolvedValue(
      err({ code: "conflict", message: "delete rejected" }),
    );
    vi.mocked(adminService.updateChunk).mockResolvedValue(
      ok({ message: "chunk updated", chunk_ids: ["chunk-1"] }),
    );
    renderWithSelectedChunk();

    await userEvent.click(
      await screen.findByRole("button", { name: "Supprimer le chunk" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: /Éditer/ }));
    await userEvent.click(screen.getByRole("button", { name: /Sauvegarder/ }));

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("shows the similar-chunks failure without hiding the chunk detail", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(
      err({ code: "server_error", message: "similar failed" }),
    );
    renderWithSelectedChunk();

    expect(await screen.findByRole("alert")).toHaveTextContent(SERVER_COPY);
    expect(screen.getByText(chunkDetail.text)).toBeInTheDocument();
  });

  it("renders the similar chunks when that query succeeded", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(
      ok(similarChunks),
    );
    renderWithSelectedChunk();

    expect(await screen.findByText(/Isolation des planchers bas/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("ChunkDetail — affichage et navigation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(ok([]));
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
  });

  it("affiche le score qualité, les métadonnées, la section, la hiérarchie et les mots-clés", async () => {
    renderWithSelectedChunk();

    expect(await screen.findByText("82%")).toBeInTheDocument();
    expect(screen.getByText("CCTP-lot-3.pdf")).toBeInTheDocument();
    expect(screen.getByText("p.4 / pos.12")).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
    expect(screen.getByText("cctp")).toBeInTheDocument();
    expect(screen.getByText("820 chars")).toBeInTheDocument();
    expect(screen.getByText("specification")).toBeInTheDocument();
    expect(screen.getByText("5.2 Isolation")).toBeInTheDocument();
    expect(screen.getByText("5 Enveloppe")).toBeInTheDocument();
    expect(screen.getByText("isolation")).toBeInTheDocument();
    expect(screen.getByText("murs")).toBeInTheDocument();
  });

  it("n'affiche pas le bloc score qualité quand quality_score est null", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(
      ok({ ...chunkDetail, quality_score: null }),
    );
    renderWithSelectedChunk();

    await screen.findByText(chunkDetail.text);
    expect(screen.queryByText("Qualité")).not.toBeInTheDocument();
  });

  it("n'affiche aucune section Hiérarchie quand parent_sections est vide", async () => {
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(
      ok({ ...chunkDetail, parent_sections: [] }),
    );
    renderWithSelectedChunk();

    await screen.findByText(chunkDetail.text);
    expect(screen.queryByText("Hiérarchie")).not.toBeInTheDocument();
  });

  it("cliquer sur un chunk adjacent appelle selectChunk avec son id", async () => {
    renderWithSelectedChunk();

    await userEvent.click(await screen.findByText("Doublage"));

    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-2");
  });

  it("cliquer sur un chunk similaire appelle selectChunk avec son id", async () => {
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(
      ok(similarChunks),
    );
    renderWithSelectedChunk();

    await userEvent.click(
      await screen.findByText(/Isolation des planchers bas/),
    );

    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-9");
  });
});
