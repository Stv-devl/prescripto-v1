import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { failureWithCode, stats } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { StatsOverview } from "./StatsOverview";

vi.mock("../services/admin.service");

const ENRICH_BUTTON = /Re-enrichir les keywords/;

describe("StatsOverview — a failed load says so instead of rendering nothing", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("renders the failure instead of nothing at all when the statistics request failed", () => {
    renderWithProviders(
      <StatsOverview
        stats={undefined}
        isPending={false}
        projectId="p-1"
        error={failureWithCode("server_error")}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("keeps the statistics on screen and shows the failure above them when a refetch fails", () => {
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={failureWithCode("network_error")}
      />,
    );

    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Erreur de connexion");
  });

  it("renders the statistics when the request succeeded", () => {
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the keyword re-enrichment failure under the button that triggered it", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      err({ code: "server_error", message: "enrich failed" }),
    );
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("does not show the enrichment report when the mutation failed", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      err({ code: "server_error", message: "enrich failed" }),
    );
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));

    await screen.findByRole("alert");
    expect(screen.queryByText(/chunks enrichis avec des keywords/)).not.toBeInTheDocument();
  });

  it("drops the previous success report when a second enrichment fails, instead of showing both", async () => {
    vi.mocked(adminService.batchEnrichKeywords)
      .mockResolvedValueOnce(ok({ updated_count: 7, message: "done" }))
      .mockResolvedValue(err({ code: "server_error", message: "enrich failed" }));
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));
    await screen.findByText(/7 chunks enrichis avec des keywords/);

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));

    await screen.findByRole("alert");
    expect(screen.queryByText(/7 chunks enrichis avec des keywords/)).not.toBeInTheDocument();
  });

  it("shows the enrichment report when the mutation succeeded", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      ok({ updated_count: 7, message: "done" }),
    );
    renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));

    expect(await screen.findByText(/7 chunks enrichis avec des keywords/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("hands the enrichment failure back to the banner once StatsOverview unmounts", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      err({ code: "server_error", message: "enrich failed" }),
    );
    const { unmount } = renderWithProviders(
      <StatsOverview
        stats={stats}
        isPending={false}
        projectId="p-1"
        error={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: ENRICH_BUTTON }));
    await screen.findByRole("alert");
    expect(useAdminStore.getState().actionFailureClaimants).toBe(1);

    unmount();

    expect(useAdminStore.getState().actionFailure?.kind).toBe("enrich");
    expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
  });

  it("renders the skeleton during the initial load", () => {
    renderWithProviders(
      <StatsOverview
        stats={undefined}
        isPending={true}
        projectId="p-1"
        error={null}
      />,
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("128")).not.toBeInTheDocument();
  });
});

const statsWithDocumentError = {
  ...stats,
  quality_alerts: { ...stats.quality_alerts, documents_with_errors: 1 },
};
const statsWithOversized = {
  ...stats,
  quality_alerts: { ...stats.quality_alerts, chunks_oversized: 3 },
};
const statsWithNoAlerts = {
  ...stats,
  quality_alerts: {
    chunks_without_keywords: 0,
    chunks_heading_only: 0,
    chunks_very_short: 0,
    chunks_oversized: 0,
    documents_with_errors: 0,
  },
};

describe("StatsOverview — cartes KPI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("affiche le nombre de documents indexés", () => {
    renderWithProviders(
      <StatsOverview stats={stats} isPending={false} projectId="p-1" error={null} />,
    );

    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("affiche la taille moyenne calculée, pondérée par le nombre de chunks par document", () => {
    renderWithProviders(
      <StatsOverview stats={stats} isPending={false} projectId="p-1" error={null} />,
    );

    // hand-computed from the fixture: (780 * 64 + 810 * 64) / 128 = 795
    expect(screen.getByText("795")).toBeInTheDocument();
  });

  it("affiche le score qualité arrondi en pourcentage", () => {
    renderWithProviders(
      <StatsOverview stats={stats} isPending={false} projectId="p-1" error={null} />,
    );

    expect(screen.getByText("74")).toBeInTheDocument();
  });

  it("affiche le total d'alertes qualité, somme des 5 catégories", () => {
    renderWithProviders(
      <StatsOverview stats={stats} isPending={false} projectId="p-1" error={null} />,
    );

    // hand-computed from the fixture: 7 + 1 + 2 + 0 + 0 = 10
    expect(screen.getByText("10")).toBeInTheDocument();
  });
});

describe("StatsOverview — alertes qualité", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("cliquer sur un bouton de filtre d'alerte met à jour les filtres et bascule l'onglet actif sur table", async () => {
    renderWithProviders(
      <StatsOverview stats={stats} isPending={false} projectId="p-1" error={null} />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Sans keywords/ }));

    expect(useAdminStore.getState().filters).toMatchObject({ has_keywords: false });
    expect(useAdminStore.getState().activeTab).toBe("table");
  });

  it("affiche le badge Documents en erreur quand documents_with_errors est positif", () => {
    renderWithProviders(
      <StatsOverview stats={statsWithDocumentError} isPending={false} projectId="p-1" error={null} />,
    );

    expect(screen.getByText(/Documents en erreur/)).toBeInTheDocument();
  });

  it("affiche le bouton Oversized quand chunks_oversized est positif, et son clic filtre par min_chars", async () => {
    renderWithProviders(
      <StatsOverview stats={statsWithOversized} isPending={false} projectId="p-1" error={null} />,
    );

    await userEvent.click(screen.getByRole("button", { name: /Oversized/ }));

    expect(useAdminStore.getState().filters).toMatchObject({ min_chars: 2500 });
    expect(useAdminStore.getState().activeTab).toBe("table");
  });

  it("n'affiche aucune section d'alertes qualité quand les 5 compteurs sont à zéro", () => {
    renderWithProviders(
      <StatsOverview stats={statsWithNoAlerts} isPending={false} projectId="p-1" error={null} />,
    );

    expect(screen.queryByRole("heading", { name: "Alertes qualité" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sans keywords/ })).not.toBeInTheDocument();
  });
});
