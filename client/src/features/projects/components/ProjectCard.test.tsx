import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import type { Project } from "../types/types";
import { ProjectCard } from "./ProjectCard";

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

function favouriteIcon(name: string): SVGElement {
  const button = screen.getByRole("button", { name });
  const icon = button.querySelector("svg");
  if (icon === null) throw new Error(`No icon inside the "${name}" button`);
  return icon;
}

describe("ProjectCard — the favourite control", () => {
  it("offers to add a project that is not a favourite", () => {
    renderWithProviders(
      <ProjectCard project={aProject()} onToggleFavorite={vi.fn()} />,
    );

    expect(
      screen.getByRole("button", { name: "Ajouter aux favoris" }),
    ).toBeVisible();
  });

  it("offers to remove a project that already is one", () => {
    renderWithProviders(
      <ProjectCard
        project={aProject({ is_favorite: true })}
        onToggleFavorite={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Retirer des favoris" }),
    ).toBeVisible();
  });

  it("reports the toggle for this project when the control is activated", async () => {
    const onToggleFavorite = vi.fn();
    renderWithProviders(
      <ProjectCard
        project={aProject({ id: "p-42" })}
        onToggleFavorite={onToggleFavorite}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Ajouter aux favoris" }),
    );

    expect(onToggleFavorite).toHaveBeenCalledWith("p-42");
  });

  it("marks the favourite with a bookmark", () => {
    renderWithProviders(
      <ProjectCard project={aProject()} onToggleFavorite={vi.fn()} />,
    );

    expect(
      favouriteIcon("Ajouter aux favoris").classList.contains(
        "lucide-bookmark",
      ),
    ).toBe(true);
  });

  it("fills the bookmark of a favourite, and only of a favourite", () => {
    const { unmount } = renderWithProviders(
      <ProjectCard project={aProject()} onToggleFavorite={vi.fn()} />,
    );
    const plain = favouriteIcon("Ajouter aux favoris").getAttribute("class");
    unmount();

    renderWithProviders(
      <ProjectCard
        project={aProject({ is_favorite: true })}
        onToggleFavorite={vi.fn()}
      />,
    );
    const marked = favouriteIcon("Retirer des favoris").getAttribute("class");

    expect(marked).toContain("fill-");
    expect(plain).not.toContain("fill-");
  });

  it("renders no favourite control when the card cannot toggle one", () => {
    renderWithProviders(<ProjectCard project={aProject()} />);

    expect(
      screen.queryByRole("button", { name: /favoris/ }),
    ).not.toBeInTheDocument();
  });
});
