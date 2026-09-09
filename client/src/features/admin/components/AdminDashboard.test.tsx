import { cleanup, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceFailure, err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import userEvent from "@testing-library/user-event";
import * as adminService from "../services/admin.service";
import { chunkDetail, chunkPage, stats, syncCheck } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { AdminDashboard } from "./AdminDashboard";

type AdminTab = Parameters<
  ReturnType<typeof useAdminStore.getState>["setActiveTab"]
>[0];

vi.mock("../services/admin.service");

const STATS_COPY = "Accès refusé";
const CHUNKS_COPY = "Le service est momentanément indisponible. Réessayez.";

/**
 * Arms the two dashboard queries with distinct error codes, so a swapped prop
 * shows up as the wrong French copy rather than as no copy at all.
 */
function armDistinctFailures(): void {
  vi.mocked(adminService.getChunkStats).mockResolvedValue(
    err({ code: "forbidden", message: "stats forbidden" }),
  );
  vi.mocked(adminService.listChunks).mockResolvedValue(
    err({ code: "server_error", message: "chunks failed" }),
  );
}

function renderOnTab(tab: AdminTab): void {
  useAdminStore.getState().setActiveTab(tab);
  renderWithProviders(<AdminDashboard projectId="p-1" />);
}

describe("AdminDashboard — each query's failure reaches the surface that shows its data", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
  });

  it("shows the stats failure and not the chunks failure on the Dashboard tab", async () => {
    armDistinctFailures();
    renderOnTab("dashboard");

    expect(await screen.findByText(STATS_COPY)).toBeInTheDocument();
    expect(screen.queryByText(CHUNKS_COPY)).not.toBeInTheDocument();
  });

  it("shows the chunks failure and not the stats failure on the Table tab", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(ok(stats));
    vi.mocked(adminService.listChunks).mockResolvedValue(
      err({ code: "server_error", message: "chunks failed" }),
    );
    renderOnTab("table");

    expect(await screen.findByText(CHUNKS_COPY)).toBeInTheDocument();
    expect(screen.queryByText(STATS_COPY)).not.toBeInTheDocument();
  });

  it("says the statistics failed on the Document tab, instead of an empty silent document picker", async () => {
    armDistinctFailures();
    renderOnTab("document");

    expect(await screen.findByText(STATS_COPY)).toBeInTheDocument();
  });

  it("says the statistics failed on the Playground tab, instead of empty silent Lot and Content type lists", async () => {
    armDistinctFailures();
    renderOnTab("playground");

    expect(await screen.findByText(STATS_COPY)).toBeInTheDocument();
  });

  it("does not repeat the stats failure on the Dashboard tab, where StatsOverview already carries it", async () => {
    armDistinctFailures();
    renderOnTab("dashboard");

    await screen.findByText(STATS_COPY);
    await waitFor(() => {
      expect(screen.getAllByText(STATS_COPY)).toHaveLength(1);
    });
  });

  it("keeps the chunk table visible when only the statistics failed", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "forbidden", message: "stats forbidden" }),
    );
    vi.mocked(adminService.listChunks).mockResolvedValue(ok(chunkPage));
    renderOnTab("table");

    expect(await screen.findByText("CCTP-lot-3.pdf")).toBeInTheDocument();
    expect(screen.getByText(STATS_COPY)).toBeInTheDocument();
  });

  it("stays silent about the statistics on the Sync tab, whose content derives from the sync check alone", async () => {
    armDistinctFailures();
    vi.mocked(adminService.getSyncCheck).mockResolvedValue(ok(syncCheck));
    renderOnTab("sync");

    await screen.findByText("CCTP-lot-3.pdf");
    expect(screen.queryByText(STATS_COPY)).not.toBeInTheDocument();
  });

  it("says a shared outage once on the Table tab, where the chunk table already carries the same cause", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    vi.mocked(adminService.listChunks).mockResolvedValue(
      err({ code: "server_error", message: "chunks failed" }),
    );
    renderOnTab("table");

    await screen.findByText(CHUNKS_COPY);
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  it("still says the statistics failed on the Table tab when the chunk list failed for another reason", async () => {
    armDistinctFailures();
    renderOnTab("table");

    expect(await screen.findByText(STATS_COPY)).toBeInTheDocument();
    expect(screen.getByText(CHUNKS_COPY)).toBeInTheDocument();
  });

  it("says a shared outage once on the Document tab, where the document's chunks carry the same cause", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(
      err({ code: "server_error", message: "document chunks failed" }),
    );
    useAdminStore.getState().setSelectedDocument("doc-1");
    renderOnTab("document");

    await screen.findByText(CHUNKS_COPY);
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });
});

describe("AdminDashboard — the side panel belongs to the chunk it shows", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.getChunkStats).mockResolvedValue(ok(stats));
    vi.mocked(adminService.listChunks).mockResolvedValue(ok(chunkPage));
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(ok([]));
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
  });

  /** Opens the panel on chunk-1 and leaves a refused deletion on screen. */
  async function armRefusedDelete(): Promise<void> {
    vi.mocked(adminService.deleteChunk).mockResolvedValue(
      err({ code: "conflict", message: "delete rejected" }),
    );
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Supprimer le chunk" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    await screen.findByRole("alert");
  }

  it("hands the failure back to the banner when the panel that showed it moves to another chunk", async () => {
    await armRefusedDelete();

    await userEvent.click(screen.getByRole("button", { name: /Doublage/ }));

    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-2");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cette donnée existe déjà",
    );
    expect(
      screen.getByRole("button", { name: "Masquer cette erreur" }),
    ).toBeInTheDocument();
  });

  it("disarms the delete confirmation when another chunk is opened from the panel", async () => {
    await armRefusedDelete();

    await userEvent.click(screen.getByRole("button", { name: /Doublage/ }));

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Supprimer" }),
      ).not.toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: "Supprimer le chunk" }),
    ).toBeInTheDocument();
  });

  it("lets the user leave a chunk mid-save and still reports the failure that lands after", async () => {
    const rejectUpdate = armHungMutation("updateChunk");

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    await userEvent.click(screen.getByRole("button", { name: /Sauvegarder/ }));

    await userEvent.click(screen.getByRole("button", { name: /Doublage/ }));
    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-2");

    rejectUpdate();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });

  it("drops an in-progress edit when another chunk is opened from the panel", async () => {
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    await userEvent.clear(screen.getByRole("textbox"));
    await userEvent.type(screen.getByRole("textbox"), "texte de chunk-1");

    await userEvent.click(screen.getByRole("button", { name: /Doublage/ }));

    await waitFor(() => {
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });
    expect(screen.queryByText("texte de chunk-1")).not.toBeInTheDocument();
  });

  it("says an action failure once while the panel that owns it is still open", async () => {
    vi.mocked(adminService.updateChunk).mockResolvedValue(
      err({ code: "server_error", message: "update failed" }),
    );
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    await userEvent.click(screen.getByRole("button", { name: /Sauvegarder/ }));

    await screen.findByRole("alert");
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  /** Opens the panel on chunk-1 and hands back the rejector of a hung mutation. */
  function armHungMutation(
    mutation: "updateChunk" | "splitChunk" | "mergeChunks",
  ): () => void {
    let reject: (() => void) | undefined;
    vi.mocked(adminService[mutation]).mockReturnValue(
      new Promise((resolve) => {
        reject = () =>
          resolve(err({ code: "server_error", message: `${mutation} failed` }));
      }),
    );
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    return () => reject?.();
  }

  it("reports an update that failed after the panel was closed", async () => {
    const rejectUpdate = armHungMutation("updateChunk");

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    await userEvent.click(screen.getByRole("button", { name: /Sauvegarder/ }));
    await userEvent.keyboard("{Escape}");

    rejectUpdate();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });

  it("reports a split that failed after the panel was closed", async () => {
    const rejectSplit = armHungMutation("splitChunk");

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    (screen.getByRole("textbox") as HTMLTextAreaElement).setSelectionRange(10, 10);
    await userEvent.click(screen.getByRole("button", { name: /Scinder/ }));
    await userEvent.keyboard("{Escape}");

    rejectSplit();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });

  it("reports a merge that failed after the panel was closed", async () => {
    const rejectMerge = armHungMutation("mergeChunks");

    await userEvent.click(
      await screen.findByRole("button", { name: /Fusionner/ }),
    );
    await userEvent.keyboard("{Escape}");

    rejectMerge();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });

  it("reports a chunk deletion that failed after the panel was closed", async () => {
    let rejectDelete: (() => void) | undefined;
    vi.mocked(adminService.deleteChunk).mockReturnValue(
      new Promise((resolve) => {
        rejectDelete = () =>
          resolve(err({ code: "server_error", message: "delete failed" }));
      }),
    );
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Supprimer le chunk" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    await userEvent.keyboard("{Escape}");
    expect(useAdminStore.getState().selectedChunkId).toBeNull();

    rejectDelete?.();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });
});

describe("AdminDashboard — a failure whose surface is gone is still reported", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.getChunkStats).mockResolvedValue(ok(stats));
    vi.mocked(adminService.listChunks).mockResolvedValue(ok(chunkPage));
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
  });

  /** Starts a re-chunk that has not settled, on the Document tab. */
  async function armPendingRechunk(): Promise<() => void> {
    let reject: (() => void) | undefined;
    vi.mocked(adminService.rechunkDocument).mockReturnValue(
      new Promise((resolve) => {
        reject = () =>
          resolve(err({ code: "server_error", message: "rechunk failed" }));
      }),
    );
    useAdminStore.getState().setActiveTab("document");
    useAdminStore.getState().setSelectedDocument("doc-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(
      await screen.findByRole("button", { name: /Re-chunker/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    return () => reject?.();
  }

  it("reports a re-chunk failure that landed after the user switched tab", async () => {
    const rejectRechunk = await armPendingRechunk();

    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    expect(useAdminStore.getState().activeTab).toBe("table");

    rejectRechunk();

    expect(await screen.findByRole("alert")).toHaveTextContent(CHUNKS_COPY);
  });

  it("clears the reported failure when the user dismisses it", async () => {
    const rejectRechunk = await armPendingRechunk();
    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    rejectRechunk();
    await screen.findByRole("alert");

    await userEvent.click(
      screen.getByRole("button", { name: "Masquer cette erreur" }),
    );

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("drops the reported failure as soon as a new attempt starts", async () => {
    const rejectRechunk = await armPendingRechunk();
    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    rejectRechunk();
    await screen.findByRole("alert");

    vi.mocked(adminService.rechunkDocument).mockReturnValue(
      new Promise(() => {}),
    );
    await userEvent.click(screen.getByRole("tab", { name: "Document" }));
    await userEvent.click(
      await screen.findByRole("button", { name: /Re-chunker/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("drops the reported failure when the action finally succeeds", async () => {
    const rejectRechunk = await armPendingRechunk();
    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    rejectRechunk();
    await screen.findByRole("alert");

    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      ok({
        message: "document re-chunked",
        old_count: 10,
        new_count: 12,
        old_avg_chars: 700,
        new_avg_chars: 640,
      }),
    );
    await userEvent.click(screen.getByRole("tab", { name: "Document" }));
    await userEvent.click(
      await screen.findByRole("button", { name: /Re-chunker/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    await screen.findByText("Re-chunking terminé");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not show a failure that belongs to another project", async () => {
    const rejectRechunk = await armPendingRechunk();
    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    rejectRechunk();
    await screen.findByRole("alert");

    cleanup();
    renderWithProviders(<AdminDashboard projectId="p-2" />);

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("drops a reported failure when the project changes", async () => {
    const rejectRechunk = await armPendingRechunk();
    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    rejectRechunk();
    await screen.findByRole("alert");

    useAdminStore.getState().reset();

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });
});

describe("AdminDashboard — tablist keyboard navigation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.getChunkStats).mockResolvedValue(ok(stats));
    vi.mocked(adminService.listChunks).mockResolvedValue(ok(chunkPage));
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
  });

  it("ArrowRight sur l'onglet actif active l'onglet suivant et affiche son panneau", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Dashboard" }).focus();

    await user.keyboard("{ArrowRight}");

    expect(useAdminStore.getState().activeTab).toBe("table");
    expect(await screen.findByText("CCTP-lot-3.pdf")).toBeInTheDocument();
  });

  it("ArrowLeft sur l'onglet actif active l'onglet précédent et affiche son panneau", async () => {
    const user = userEvent.setup();
    useAdminStore.getState().setActiveTab("table");
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Table" }).focus();

    await user.keyboard("{ArrowLeft}");

    expect(useAdminStore.getState().activeTab).toBe("dashboard");
  });

  it("Home puis Fin activent respectivement le premier et le dernier onglet", async () => {
    const user = userEvent.setup();
    useAdminStore.getState().setActiveTab("table");
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Table" }).focus();

    await user.keyboard("{Home}");
    expect(useAdminStore.getState().activeTab).toBe("dashboard");

    screen.getByRole("tab", { name: "Dashboard" }).focus();
    await user.keyboard("{End}");
    expect(useAdminStore.getState().activeTab).toBe("sync");
  });

  it("après ArrowRight, le focus DOM est sur le bouton du nouvel onglet actif", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Dashboard" }).focus();

    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Table" })).toHaveFocus();
  });

  it("après Home, le focus DOM est sur le premier onglet ; après Fin, sur le dernier", async () => {
    const user = userEvent.setup();
    useAdminStore.getState().setActiveTab("table");
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Table" }).focus();

    await user.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Dashboard" })).toHaveFocus();

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Sync" })).toHaveFocus();
  });

  it("après un changement d'onglet au clavier, seul l'onglet actif porte tabIndex 0", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Dashboard" }).focus();

    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Table" })).toHaveAttribute(
      "tabindex",
      "0",
    );
    for (const label of ["Dashboard", "Document", "Playground", "Sync"]) {
      expect(screen.getByRole("tab", { name: label })).toHaveAttribute(
        "tabindex",
        "-1",
      );
    }
  });

  it("chaque panneau porte role=tabpanel et est associé à son onglet dans les deux sens", () => {
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    const tab = screen.getByRole("tab", { name: "Dashboard" });
    const panel = screen.getByRole("tabpanel");

    expect(tab).toHaveAttribute("aria-controls", panel.id);
    expect(panel).toHaveAttribute("aria-labelledby", tab.id);
  });

  it("survoler un onglet sans clic ni touche n'active pas l'onglet", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await user.hover(screen.getByRole("tab", { name: "Table" }));

    expect(useAdminStore.getState().activeTab).toBe("dashboard");
  });

  it("ArrowRight sur le dernier onglet boucle vers le premier", async () => {
    const user = userEvent.setup();
    useAdminStore.getState().setActiveTab("sync");
    renderWithProviders(<AdminDashboard projectId="p-1" />);
    screen.getByRole("tab", { name: "Sync" }).focus();

    await user.keyboard("{ArrowRight}");

    expect(useAdminStore.getState().activeTab).toBe("dashboard");
  });
});

describe("AdminDashboard — the action-failure banner dedups with stats and escapes the tree", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.getChunkStats).mockResolvedValue(ok(stats));
    vi.mocked(adminService.listChunks).mockResolvedValue(ok(chunkPage));
    vi.mocked(adminService.listDocumentChunks).mockResolvedValue(ok([]));
    vi.mocked(adminService.getChunkDetail).mockResolvedValue(ok(chunkDetail));
    vi.mocked(adminService.findSimilarChunks).mockResolvedValue(ok([]));
  });

  it("ne montre l'échec qu'une seule fois quand la panne de stats et l'échec d'action partagent le même code, sur l'onglet Playground", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "delete failed" }),
      "p-1",
      "delete",
    );
    renderOnTab("playground");

    await screen.findByRole("alert");
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  it("ne montre l'échec qu'une seule fois quand la panne de stats et l'échec d'action partagent le même code, sur l'onglet Dashboard", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "rechunk failed" }),
      "p-1",
      "rechunk",
    );
    renderOnTab("dashboard");

    await screen.findByRole("alert");
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  it("le dédoublonnage stats/bandeau s'applique aussi sur l'onglet Table", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "delete failed" }),
      "p-1",
      "delete",
    );
    renderOnTab("table");

    await screen.findByRole("alert");
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  it("le dédoublonnage stats/bandeau s'applique aussi sur l'onglet Document", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "server_error", message: "stats failed" }),
    );
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "rechunk failed" }),
      "p-1",
      "rechunk",
    );
    renderOnTab("document");

    await screen.findByRole("alert");
    await waitFor(() => {
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });
  });

  it("n'efface rien quand la panne de stats et l'échec d'action ont des codes différents", async () => {
    vi.mocked(adminService.getChunkStats).mockResolvedValue(
      err({ code: "forbidden", message: "stats forbidden" }),
    );
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "delete failed" }),
      "p-1",
      "delete",
    );
    renderOnTab("playground");

    expect(await screen.findByText(STATS_COPY)).toBeInTheDocument();
    expect(screen.getByText(CHUNKS_COPY)).toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });

  it("affiche le libellé de l'action au-dessus du message d'erreur dans le bandeau", async () => {
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "conflict", message: "delete rejected" }),
      "p-1",
      "delete",
    );
    renderOnTab("dashboard");

    const label = await screen.findByText("Échec de la suppression du chunk");
    const alert = screen.getByRole("alert");
    expect(
      label.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("rend le bandeau hors de l'arbre React d'AdminDashboard (preuve du createPortal)", async () => {
    useAdminStore.getState().reportActionFailure(
      new ServiceFailure({ code: "server_error", message: "delete failed" }),
      "p-1",
      "delete",
    );
    const { container } = renderWithProviders(
      <AdminDashboard projectId="p-1" />,
    );

    const alert = await screen.findByRole("alert");
    expect(container.contains(alert)).toBe(false);
    expect(document.body.contains(alert)).toBe(true);
  });

  it("garde le bandeau muet tant qu'un panneau ou une vue du document affiche encore sa propre erreur, et le relâche quand les deux sont partis", async () => {
    let rejectUpdate: (() => void) | undefined;
    vi.mocked(adminService.updateChunk).mockReturnValue(
      new Promise((resolve) => {
        rejectUpdate = () =>
          resolve(err({ code: "server_error", message: "update failed" }));
      }),
    );
    let rejectRechunk: (() => void) | undefined;
    vi.mocked(adminService.rechunkDocument).mockReturnValue(
      new Promise((resolve) => {
        rejectRechunk = () =>
          resolve(err({ code: "server_error", message: "rechunk failed" }));
      }),
    );
    useAdminStore.getState().setActiveTab("document");
    useAdminStore.getState().setSelectedDocument("doc-1");
    useAdminStore.getState().selectChunk("chunk-1");
    renderWithProviders(<AdminDashboard projectId="p-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Éditer/ }));
    await userEvent.click(screen.getByRole("button", { name: /Sauvegarder/ }));
    await userEvent.click(
      await screen.findByRole("button", { name: /Re-chunker/ }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirmer" }));

    rejectUpdate?.();
    rejectRechunk?.();
    await waitFor(() => {
      expect(useAdminStore.getState().actionFailureClaimants).toBe(2);
    });
    expect(
      screen.queryByRole("button", { name: "Masquer cette erreur" }),
    ).not.toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(useAdminStore.getState().actionFailureClaimants).toBe(1);
    });
    expect(
      screen.queryByRole("button", { name: "Masquer cette erreur" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Table" }));
    await waitFor(() => {
      expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
    });
    expect(
      await screen.findByRole("button", { name: "Masquer cette erreur" }),
    ).toBeInTheDocument();
  });
});
