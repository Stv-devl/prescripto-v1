import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { duplicates, noDuplicates } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { DuplicateDetection } from "./DuplicateDetection";

vi.mock("../services/admin.service");

const HARDCODED_COPY = "Erreur lors de la détection des doublons.";
const EMPTY_COPY = /Aucun doublon détecté/;

describe("DuplicateDetection — the copy comes from userMessageFor, not from the component", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("renders the mapped French copy on a failure, not the sentence hardcoded in the component", async () => {
    vi.mocked(adminService.detectDuplicates).mockResolvedValue(
      err({ code: "forbidden", message: "duplicates forbidden" }),
    );
    renderWithProviders(
      <DuplicateDetection projectId="p-1" documentId="doc-1" />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Accès refusé");
    expect(screen.queryByText(HARDCODED_COPY)).not.toBeInTheDocument();
  });

  it("renders the duplicate pairs when the request succeeded", async () => {
    vi.mocked(adminService.detectDuplicates).mockResolvedValue(ok(duplicates));
    renderWithProviders(
      <DuplicateDetection projectId="p-1" documentId="doc-1" />,
    );

    expect(await screen.findByText(/64 chunks analysés/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders « Aucun doublon détecté » when the request returned zero pairs and no error", async () => {
    vi.mocked(adminService.detectDuplicates).mockResolvedValue(ok(noDuplicates));
    renderWithProviders(
      <DuplicateDetection projectId="p-1" documentId="doc-1" />,
    );

    expect(await screen.findByText(EMPTY_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("stays as talkative as before the change when a refetch fails over kept pairs", async () => {
    vi.mocked(adminService.detectDuplicates)
      .mockResolvedValueOnce(ok(noDuplicates))
      .mockResolvedValue(err({ code: "network_error", message: "offline" }));
    const { queryClient } = renderWithProviders(
      <DuplicateDetection projectId="p-1" documentId="doc-1" />,
    );

    await screen.findByText(EMPTY_COPY);
    await queryClient.invalidateQueries();

    expect(await screen.findByRole("alert")).toHaveTextContent("Erreur de connexion");
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });
});
