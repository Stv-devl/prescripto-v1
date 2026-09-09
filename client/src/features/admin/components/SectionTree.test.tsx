import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { sectionTree } from "../testFixtures";
import type { SectionNode } from "../types/types";
import { SectionTree } from "./SectionTree";

/**
 * The shared `sectionTree` fixture is a single childless root — it cannot
 * exercise `aria-expanded` at all. Two levels, root repliable and expanded by
 * default (depth 0), child repliable and collapsed by default (depth 1).
 */
const treeWithChildren: SectionNode[] = [
  {
    title: "Root",
    chunk_count: 10,
    children: [
      {
        title: "Child",
        chunk_count: 5,
        children: [{ title: "Leaf", chunk_count: 2, children: [] }],
      },
    ],
  },
];

vi.mock("../services/admin.service");

const EMPTY_COPY = "Aucune section trouvée.";

describe("SectionTree — « no section » must not stand in for a failed tree", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the failure instead of « Aucune section trouvée. » when the tree request failed", async () => {
    vi.mocked(adminService.getSectionTree).mockResolvedValue(
      err({ code: "server_error", message: "tree failed" }),
    );
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });

  it("renders the failure instead of the empty copy when a refetch fails over a cached empty tree", async () => {
    vi.mocked(adminService.getSectionTree)
      .mockResolvedValueOnce(ok([]))
      .mockResolvedValue(err({ code: "network_error", message: "offline" }));
    const { queryClient } = renderWithProviders(
      <SectionTree projectId="p-1" onSelect={vi.fn()} />,
    );

    await screen.findByText(EMPTY_COPY);
    await queryClient.invalidateQueries();

    expect(await screen.findByRole("alert")).toHaveTextContent("Erreur de connexion");
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });

  it("renders the sections when the request succeeded", async () => {
    vi.mocked(adminService.getSectionTree).mockResolvedValue(ok(sectionTree));
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);

    expect(await screen.findByText("5 Enveloppe")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders « Aucune section trouvée. » when the tree came back empty and no error", async () => {
    vi.mocked(adminService.getSectionTree).mockResolvedValue(ok([]));
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);

    expect(await screen.findByText(EMPTY_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("SectionTree — aria-expanded", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(adminService.getSectionTree).mockResolvedValue(ok(treeWithChildren));
  });

  it("un nœud avec enfants, initialement dévoilé (profondeur 0), porte aria-expanded=true", async () => {
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);

    expect(await screen.findByRole("button", { name: /Root/ })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("un nœud avec enfants, initialement replié (profondeur ≥ 1), porte aria-expanded=false", async () => {
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);

    expect(await screen.findByRole("button", { name: /Child/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("cliquer un nœud replié bascule son aria-expanded à true", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);
    const child = await screen.findByRole("button", { name: /Child/ });

    await user.click(child);

    expect(child).toHaveAttribute("aria-expanded", "true");
  });

  it("cliquer un nœud déjà déplié le rebascule à false", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);
    const root = await screen.findByRole("button", { name: /Root/ });

    await user.click(root);

    expect(root).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Child")).not.toBeInTheDocument();
  });

  it("un nœud enfant (profondeur 1, imbriqué) porte aria-expanded correctement, indépendamment de l'état de son parent", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);
    const root = await screen.findByRole("button", { name: /Root/ });
    const child = screen.getByRole("button", { name: /Child/ });

    await user.click(child);

    expect(child).toHaveAttribute("aria-expanded", "true");
    expect(root).toHaveAttribute("aria-expanded", "true");
  });

  it("une feuille (sans enfants) ne porte aucun attribut aria-expanded", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SectionTree projectId="p-1" onSelect={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /Child/ }));

    expect(screen.getByRole("button", { name: /Leaf/ })).not.toHaveAttribute(
      "aria-expanded",
    );
  });
});
