import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import type { Project } from "../types/types";
import { ProjectListTable } from "./ProjectListTable";

function aProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "p-1",
    tenant_id: "t-1",
    name: "Groupe scolaire Jean Moulin",
    phase: "PRO",
    status: "active",
    address: "12 rue des Lilas",
    client: "Ville de Tours",
    architect: "Atelier Nord",
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
    document_count: 4,
    created_at: "2026-03-12T09:00:00Z",
    updated_at: "2026-03-12T09:00:00Z",
    ...overrides,
  };
}

function renderTable(project: Project, onToggleFavorite = vi.fn()) {
  return renderWithProviders(
    <ProjectListTable
      projects={[project]}
      onDelete={vi.fn()}
      onArchive={vi.fn()}
      onToggleFavorite={onToggleFavorite}
    />,
  );
}

// Rows are `motion.tr` with `initial={{ opacity: 0 }}`, and framer-motion does
// not settle under jsdom: the row stays at opacity 0, so `toBeVisible` reports
// false for reasons that have nothing to do with this component. Querying by
// role and name already proves the accessible name, which is what is at stake.
describe("ProjectListTable — the favourite control", () => {
  it("offers to add a project that is not a favourite", () => {
    renderTable(aProject());

    expect(
      screen.getByRole("button", { name: "Ajouter aux favoris" }),
    ).toBeInTheDocument();
  });

  it("offers to remove a project that already is one", () => {
    renderTable(aProject({ is_favorite: true }));

    expect(
      screen.getByRole("button", { name: "Retirer des favoris" }),
    ).toBeInTheDocument();
  });

  it("reports the toggle for this project when the control is activated", async () => {
    const onToggleFavorite = vi.fn();
    renderTable(aProject({ id: "p-42" }), onToggleFavorite);

    await userEvent.click(
      screen.getByRole("button", { name: "Ajouter aux favoris" }),
    );

    expect(onToggleFavorite).toHaveBeenCalledWith("p-42");
  });

  it("marks the favourite with a bookmark, as the card view does", () => {
    renderTable(aProject());

    const icon = screen
      .getByRole("button", { name: "Ajouter aux favoris" })
      .querySelector("svg");

    expect(icon?.classList.contains("lucide-bookmark")).toBe(true);
  });

  it("fills the bookmark of a favourite, and only of a favourite", () => {
    const { unmount } = renderTable(aProject());
    const plain = screen
      .getByRole("button", { name: "Ajouter aux favoris" })
      .querySelector("svg")
      ?.getAttribute("class");
    unmount();

    renderTable(aProject({ is_favorite: true }));
    const marked = screen
      .getByRole("button", { name: "Retirer des favoris" })
      .querySelector("svg")
      ?.getAttribute("class");

    expect(marked).toContain("fill-");
    expect(plain).not.toContain("fill-");
  });
});
