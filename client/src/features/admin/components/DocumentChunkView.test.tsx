import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { chunkItem, stats } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { DocumentChunkView } from "./DocumentChunkView";

vi.mock("../services/admin.service");

const EMPTY_COPY = "Aucun chunk pour ce document.";

/** The document must be selected: without it the query is disabled and never fails. */
function renderWithSelectedDocument() {
  useAdminStore.getState().setSelectedDocument("doc-1");
  return renderWithProviders(
    <DocumentChunkView projectId="p-1" stats={stats} />,
  );
}

describe("DocumentChunkView — a failed document load says so, and keeps the picker", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("renders the failure when loading the document's chunks failed", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(
      err({ code: "server_error", message: "document chunks failed" }),
    );
    renderWithSelectedDocument();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("keeps the document picker reachable when the load failed, since it is the only way out", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(
      err({ code: "server_error", message: "document chunks failed" }),
    );
    renderWithSelectedDocument();

    await screen.findByRole("alert");
    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /CCTP-lot-5/ })).toBeInTheDocument();
  });

  it("renders the failure instead of « Aucun chunk pour ce document. » when a refetch fails over a cached empty list", async () => {
    vi.mocked(adminService.listDocumentChunks)
      .mockResolvedValueOnce(ok([]))
      .mockResolvedValue(err({ code: "network_error", message: "offline" }));
    const { queryClient } = renderWithSelectedDocument();

    await screen.findByText(EMPTY_COPY);
    await queryClient.invalidateQueries();

    expect(await screen.findByRole("alert")).toHaveTextContent("Erreur de connexion");
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });

  it("renders « Aucun chunk pour ce document. » when the document has zero chunks and no error", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
    renderWithSelectedDocument();

    expect(await screen.findByText(EMPTY_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the re-chunk failure under the button that triggered it", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      err({ code: "server_error", message: "rechunk failed" }),
    );
    renderWithSelectedDocument();

    await userEvent.click(screen.getByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("drops the previous re-chunk report when a second attempt fails, instead of showing both", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument)
      .mockResolvedValueOnce(
        ok({
          message: "document re-chunked",
          old_count: 10,
          new_count: 12,
          old_avg_chars: 700,
          new_avg_chars: 640,
        }),
      )
      .mockResolvedValue(err({ code: "server_error", message: "rechunk failed" }));
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await screen.findByText("Re-chunking terminé");

    await userEvent.click(screen.getByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    await screen.findByRole("alert");
    expect(screen.queryByText("Re-chunking terminé")).not.toBeInTheDocument();
  });

  it("does not carry the previous failure into a re-opened confirmation panel", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      err({ code: "server_error", message: "rechunk failed" }),
    );
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await userEvent.click(screen.getByRole("button", { name: /Re-chunker/ }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("still reports a re-chunk failure when the confirmation panel was closed while it was in flight", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    let rejectRechunk: (() => void) | undefined;
    vi.mocked(adminService.rechunkDocument).mockReturnValue(
      new Promise((resolve) => {
        rejectRechunk = () =>
          resolve(err({ code: "server_error", message: "rechunk failed" }));
      }),
    );
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await userEvent.click(screen.getByRole("button", { name: "Annuler" }));

    rejectRechunk?.();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("takes the re-chunk failure off this view when the user switches document, and leaves it for the banner", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      err({ code: "server_error", message: "rechunk failed" }),
    );
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await screen.findByRole("alert");

    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-2");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(useAdminStore.getState().actionFailure).not.toBeNull();
  });

  it("drops the re-chunk report of one document when the user switches to another", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      ok({
        message: "document re-chunked",
        old_count: 10,
        new_count: 12,
        old_avg_chars: 700,
        new_avg_chars: 640,
      }),
    );
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    await screen.findByText("Re-chunking terminé");

    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-2");

    expect(screen.queryByText("Re-chunking terminé")).not.toBeInTheDocument();
  });

  it("closes the armed re-chunk confirmation when the user switches document, so Confirmer cannot hit the new one", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    expect(screen.getByRole("button", { name: "Confirmer" })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-2");

    expect(screen.queryByRole("button", { name: "Confirmer" })).not.toBeInTheDocument();
  });

  it("does not show the « Re-chunking terminé » panel when the mutation failed", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      err({ code: "server_error", message: "rechunk failed" }),
    );
    renderWithSelectedDocument();

    await userEvent.click(screen.getByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    await screen.findByRole("alert");
    expect(screen.queryByText("Re-chunking terminé")).not.toBeInTheDocument();
  });

  it("lets the user switch document while a re-chunk is in flight, since its failure is reported elsewhere", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    let rejectRechunk: (() => void) | undefined;
    vi.mocked(adminService.rechunkDocument).mockReturnValue(
      new Promise((resolve) => {
        rejectRechunk = () =>
          resolve(err({ code: "server_error", message: "rechunk failed" }));
      }),
    );
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByRole("button", { name: /Re-chunker/ }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    expect(screen.getByRole("combobox")).toBeEnabled();
    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-2");
    expect(useAdminStore.getState().selectedDocumentId).toBe("doc-2");

    rejectRechunk?.();

    await waitFor(() => {
      expect(useAdminStore.getState().actionFailure).not.toBeNull();
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("DocumentChunkView — avant sélection d'un document", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("n'affiche ni squelette de chargement ni liste de chunks", () => {
    const { container } = renderWithProviders(
      <DocumentChunkView projectId="p-1" stats={stats} />,
    );

    expect(
      screen.getByText("Sélectionnez un document pour voir ses chunks dans l'ordre."),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(0);
    expect(adminService.listDocumentChunks).not.toHaveBeenCalled();
  });
});

describe("DocumentChunkView — sélection de document", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("sélectionner un document dans la liste déroulante affiche ses chunks", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    renderWithProviders(<DocumentChunkView projectId="p-1" stats={stats} />);

    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-1");

    expect(await screen.findByText(chunkItem.text_preview)).toBeInTheDocument();
    expect(useAdminStore.getState().selectedDocumentId).toBe("doc-1");
  });
});

describe("DocumentChunkView — liste de chunks", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("affiche chaque chunk avec sa position, sa page, son type de contenu et son score qualité", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    renderWithSelectedDocument();

    await screen.findByText(chunkItem.text_preview);
    expect(screen.getByText("#12")).toBeInTheDocument();
    expect(screen.getByText("p.4")).toBeInTheDocument();
    expect(screen.getByText("specification")).toBeInTheDocument();
    expect(screen.getByText("820 chars")).toBeInTheDocument();
    expect(screen.getByText("Q 82%")).toBeInTheDocument();
  });

  it("affiche un indicateur de gap entre deux chunks dont la position ou la page saute de plus de 1", async () => {
    const gappedChunk = {
      ...chunkItem,
      id: "chunk-2",
      position: 15,
      page: 4,
      text_preview: "Contenu totalement différent, sans rapport avec le chunk précédent.",
    };
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(
      ok([chunkItem, gappedChunk]),
    );
    renderWithSelectedDocument();

    expect(await screen.findByText(/Gap détecté/)).toBeInTheDocument();
  });

  it("affiche un indicateur d'overlap quand le texte de deux chunks consécutifs se chevauche sur plus de 20 caractères", async () => {
    const overlap = "abcdefghijklmnopqrstuvwxyz01234";
    const first = { ...chunkItem, text_preview: `Some preceding content here ${overlap}` };
    const second = {
      ...chunkItem,
      id: "chunk-2",
      position: 13,
      page: 4,
      text_preview: `${overlap} some following content here`,
    };
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([first, second]));
    renderWithSelectedDocument();

    expect(await screen.findByText(/Overlap/)).toBeInTheDocument();
    expect(screen.getByText(overlap)).toBeInTheDocument();
  });

  it("n'affiche ni gap ni overlap entre deux chunks contigus sans chevauchement significatif", async () => {
    const first = { ...chunkItem, text_preview: "Premier extrait, sans rapport particulier." };
    const second = {
      ...chunkItem,
      id: "chunk-2",
      position: 13,
      page: 4,
      text_preview: "Second extrait, contenu totalement différent lui aussi.",
    };
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([first, second]));
    renderWithSelectedDocument();

    await screen.findByText(second.text_preview);
    expect(screen.queryByText(/Gap détecté/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Overlap/)).not.toBeInTheDocument();
  });

  it("cliquer sur une carte de chunk appelle selectChunk avec son id", async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    renderWithSelectedDocument();

    await userEvent.click(await screen.findByText(chunkItem.text_preview));

    expect(useAdminStore.getState().selectedChunkId).toBe(chunkItem.id);
  });
});

describe("DocumentChunkView — doublons", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it('cliquer sur "Doublons" affiche DuplicateDetection pour le document sélectionné', async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.detectDuplicates).mockResolvedValue(
      ok({ total_chunks_analyzed: 2, pairs: [] }),
    );
    renderWithSelectedDocument();
    await screen.findByText(chunkItem.text_preview);

    await userEvent.click(screen.getByRole("button", { name: /Doublons/ }));

    expect(await screen.findByText("Doublons détectés")).toBeInTheDocument();
  });

  it('cliquer une seconde fois sur "Doublons" le masque', async () => {
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([chunkItem]));
    vi.mocked(adminService.detectDuplicates).mockResolvedValue(
      ok({ total_chunks_analyzed: 2, pairs: [] }),
    );
    renderWithSelectedDocument();
    await screen.findByText(chunkItem.text_preview);
    await userEvent.click(screen.getByRole("button", { name: /Doublons/ }));
    await screen.findByText("Doublons détectés");

    await userEvent.click(screen.getByRole("button", { name: /Doublons/ }));

    expect(screen.queryByText("Doublons détectés")).not.toBeInTheDocument();
  });
});
