import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { syncCheck } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { SyncStatus } from "./SyncStatus";

vi.mock("../services/admin.service");

const MISMATCH_TOGGLE = /Afficher uniquement les désynchronisations/;

describe("SyncStatus — a failed check says so instead of leaving a blank screen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("renders the failure instead of a blank screen when the sync check failed", async () => {
    vi.mocked(adminService.getSyncCheck).mockResolvedValue(
      err({ code: "server_error", message: "sync check failed" }),
    );
    renderWithProviders(<SyncStatus projectId="p-1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("keeps the mismatch toggle reachable when the check failed, since it is the only way back", async () => {
    vi.mocked(adminService.getSyncCheck).mockResolvedValue(
      err({ code: "server_error", message: "sync check failed" }),
    );
    renderWithProviders(<SyncStatus projectId="p-1" />);

    await screen.findByRole("alert");
    expect(screen.getByLabelText(MISMATCH_TOGGLE)).toBeInTheDocument();
  });

  it("keeps a way back to the previous page when the current page failed", async () => {
    const fullPage = Array.from({ length: 20 }, (_, i) => ({
      ...syncCheck.documents.items[0],
      document_id: `doc-${i}`,
    }));
    vi.mocked(adminService.getSyncCheck)
      .mockResolvedValueOnce(
        ok({
          ...syncCheck,
          documents: { ...syncCheck.documents, total: 60, items: fullPage },
        }),
      )
      .mockResolvedValue(err({ code: "server_error", message: "page failed" }));
    renderWithProviders(<SyncStatus projectId="p-1" />);

    await screen.findByText("Synchronisé");
    await userEvent.click(screen.getByRole("button", { name: "Page suivante" }));

    await screen.findByRole("alert");
    expect(
      screen.getByRole("button", { name: /Page précédente/ }),
    ).toBeInTheDocument();
  });

  it("renders the sync banner when the check succeeded", async () => {
    vi.mocked(adminService.getSyncCheck).mockResolvedValue(ok(syncCheck));
    renderWithProviders(<SyncStatus projectId="p-1" />);

    expect(await screen.findByText("Synchronisé")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the banner visible and shows the failure above it when a refetch fails", async () => {
    vi.mocked(adminService.getSyncCheck)
      .mockResolvedValueOnce(ok(syncCheck))
      .mockResolvedValue(err({ code: "network_error", message: "offline" }));
    const { queryClient } = renderWithProviders(<SyncStatus projectId="p-1" />);

    await screen.findByText("Synchronisé");
    await queryClient.invalidateQueries();

    expect(await screen.findByRole("alert")).toHaveTextContent("Erreur de connexion");
    expect(screen.getByText("Synchronisé")).toBeInTheDocument();
  });

  it("renders the skeleton during the initial load", () => {
    vi.mocked(adminService.getSyncCheck).mockReturnValue(new Promise(() => {}));
    renderWithProviders(<SyncStatus projectId="p-1" />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Synchronisé")).not.toBeInTheDocument();
  });
});
