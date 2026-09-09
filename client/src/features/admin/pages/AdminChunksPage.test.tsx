import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceFailure } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { renderWithProviders } from "@/test/utils";
import { useAdminStore } from "../stores/store";
import type { User } from "@/types/user";
// eslint-disable-next-line no-restricted-imports -- mirrors the page's own cross-feature import of useProjects (AdminChunksPage.tsx:6, disabled there for the same reason); mocking any other module would leave the real fetch running
import * as projects from "@/features/projects";
import { AdminChunksPage } from "./AdminChunksPage";

vi.mock("@/features/projects");

/** Derived from the barrel already imported above, so the seam stays a single one. */
type ProjectRow = NonNullable<
  ReturnType<typeof projects.useProjects>["data"]
>["projects"][number];

const adminUser: User = {
  id: "u-1",
  email: "stevan@example.test",
  role: "admin",
  tenant_id: "t-1",
  first_name: "Stevan",
  last_name: null,
  tenant_name: "Prescripto",
  tenant_plan: "pro",
  created_at: "2026-01-01T00:00:00Z",
};

/** A project row, filled out so the picker has something real to select. */
function project(id: string, name: string): ProjectRow {
  return {
    id,
    name,
    tenant_id: "t-1",
    phase: "conception",
    status: "en_cours",
    address: "12 rue des Lilas",
    client: "SCI Test",
    architect: "",
    architect_address: "",
    bureau_thermique: "",
    bureau_thermique_address: "",
    bureau_vrd: "",
    bureau_vrd_address: "",
    bureau_beton: "",
    bureau_beton_address: "",
    economiste: "",
    economiste_address: "",
    controleur_technique: "",
    controleur_technique_address: "",
    is_favorite: false,
    document_count: 3,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

/** The page redirects before any query unless the viewer is an admin. */
function armAdminSession(): void {
  useAuthStore.getState().setUser(adminUser);
}

function armProjects(
  result: Partial<ReturnType<typeof projects.useProjects>>,
): void {
  vi.mocked(projects.useProjects).mockReturnValue(
    result as ReturnType<typeof projects.useProjects>,
  );
}

describe("AdminChunksPage — a failed project list says so instead of an empty picker", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    armAdminSession();
  });

  it("renders the failure when the project list failed, instead of an empty picker with no explanation", () => {
    armProjects({
      data: undefined,
      isPending: false,
      error: new ServiceFailure({
        code: "server_error",
        message: "project list failed",
      }),
    });

    renderWithProviders(<AdminChunksPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("still tells the user to pick a project when the list failed — the two states are independent", () => {
    armProjects({
      data: { projects: [], total: 0 },
      isPending: false,
      error: new ServiceFailure({
        code: "network_error",
        message: "project list refetch failed",
      }),
    });

    renderWithProviders(<AdminChunksPage />);

    expect(screen.getByRole("alert")).toHaveTextContent("Erreur de connexion");
    expect(
      screen.getByText("Sélectionnez un projet pour inspecter ses chunks."),
    ).toBeInTheDocument();
  });

  it("keeps the project picker mounted when the list failed, since it is the page's only control", () => {
    armProjects({
      data: undefined,
      isPending: false,
      error: new ServiceFailure({
        code: "server_error",
        message: "project list failed",
      }),
    });

    renderWithProviders(<AdminChunksPage />);

    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Admin RAG" })).toBeInTheDocument();
  });

  it("drops the previous project's selection when another project is picked", async () => {
    armProjects({
      data: {
        projects: [project("p-1", "Chantier A"), project("p-2", "Chantier B")],
        total: 2,
      },
      isPending: false,
      error: null,
    });
    useAdminStore.getState().selectChunk("chunk-1");
    useAdminStore.getState().setSelectedDocument("doc-1");
    useAdminStore.getState().setActiveTab("document");

    renderWithProviders(<AdminChunksPage />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "p-1");

    expect(useAdminStore.getState().selectedChunkId).toBeNull();
    expect(useAdminStore.getState().selectedDocumentId).toBeNull();
    expect(useAdminStore.getState().activeTab).toBe("dashboard");
  });

  it("invites the user to pick a project when the list loaded and none is selected", () => {
    armProjects({
      data: { projects: [], total: 0 },
      isPending: false,
      error: null,
    });

    renderWithProviders(<AdminChunksPage />);

    expect(
      screen.getByText("Sélectionnez un projet pour inspecter ses chunks."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
