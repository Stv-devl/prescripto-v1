import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProjectSummaryData, SummaryProgressEvent } from "../types/types";
import * as hooks from "../hooks/hooks";
import { ProjectSummaryTab } from "./ProjectSummaryTab";

vi.mock("../hooks/hooks");

const cachedSummary: ProjectSummaryData = {
  description: "Bâtiment R+2 en zone urbaine",
  systemeConstructif: [
    {
      label: "Fondations",
      description: "Semelles filantes sur bon sol",
      kpis: ["Profondeur 0,80 m"],
      details: ["Béton C25/30"],
    },
  ],
  contraintes: [],
};

/**
 * Arms the three hooks for a project that already has a cached summary,
 * with the generation state the case is about.
 */
function armCachedSummary(generationError: string | null): void {
  vi.mocked(hooks.useSummaryStatus).mockReturnValue({
    data: { has_documents: true, has_summary: true, status: "done" },
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof hooks.useSummaryStatus>);

  vi.mocked(hooks.useSummary).mockReturnValue({
    data: {
      id: "s-1",
      project_id: "p-1",
      status: "done",
      data: cachedSummary,
      error_message: null,
      generated_at: "2026-09-01T00:00:00Z",
    },
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof hooks.useSummary>);

  vi.mocked(hooks.useSummaryGeneration).mockReturnValue({
    progress: [],
    isGenerating: false,
    generatedData: null,
    finalStatus: null,
    error: generationError,
    generate: vi.fn(),
  });
}

/** Arms all three hooks with sensible defaults, overridable per case. */
function armHooks(overrides: {
  status?: Partial<{
    data: { has_documents: boolean; has_summary: boolean; status: string };
    isPending: boolean;
    error: unknown;
  }>;
  summary?: Partial<{
    data: {
      id: string;
      project_id: string;
      status: string;
      data: ProjectSummaryData;
      error_message: string | null;
      generated_at: string;
    };
    isPending: boolean;
    error: unknown;
  }>;
  generation?: Partial<{
    progress: SummaryProgressEvent[];
    isGenerating: boolean;
    generatedData: ProjectSummaryData | null;
    finalStatus: string | null;
    error: string | null;
    generate: () => Promise<void>;
  }>;
} = {}): void {
  vi.mocked(hooks.useSummaryStatus).mockReturnValue({
    data: { has_documents: true, has_summary: false, status: "none" },
    isPending: false,
    error: null,
    ...overrides.status,
  } as unknown as ReturnType<typeof hooks.useSummaryStatus>);

  vi.mocked(hooks.useSummary).mockReturnValue({
    data: undefined,
    isPending: false,
    error: null,
    ...overrides.summary,
  } as unknown as ReturnType<typeof hooks.useSummary>);

  vi.mocked(hooks.useSummaryGeneration).mockReturnValue({
    progress: [],
    isGenerating: false,
    generatedData: null,
    finalStatus: null,
    error: null,
    generate: vi.fn(),
    ...overrides.generation,
  });
}

describe("ProjectSummaryTab — états d'entrée", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("status.isPending vrai affiche le spinner de chargement, rien d'autre", () => {
    armHooks({ status: { isPending: true } });

    const { container } = render(
      <ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />,
    );

    expect(container.querySelector("svg.animate-spin")).toBeTruthy();
    expect(screen.queryByText(/Aucun document/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("status.error non nul affiche le message d'erreur de statut", () => {
    armHooks({ status: { error: new Error("boom") } });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(
      screen.getByText("Impossible de charger le statut du résumé."),
    ).toBeInTheDocument();
  });

  it("status.data.has_documents faux affiche Aucun document", () => {
    armHooks({ status: { data: { has_documents: false, has_summary: false, status: "none" } } });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Aucun document")).toBeInTheDocument();
  });

  it("status.isPending vrai ET status.error non nul simultanément affiche le spinner, pas le message d'erreur", () => {
    armHooks({ status: { isPending: true, error: new Error("boom") } });

    const { container } = render(
      <ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />,
    );

    expect(container.querySelector("svg.animate-spin")).toBeTruthy();
    expect(
      screen.queryByText("Impossible de charger le statut du résumé."),
    ).not.toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — génération en cours", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("affiche la vue de progression avec le bon compte", () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "generating" } },
      generation: {
        isGenerating: true,
        progress: [
          { type: "progress", section: "Fondations", index: 0, total: 5, status: "done" },
          { type: "progress", section: "Élévation", index: 1, total: 5, status: "done" },
        ],
      },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("2/5 sections analysées")).toBeInTheDocument();
  });

  it("affiche le libellé de l'étape en cours issue du dernier événement de progress", () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "generating" } },
      generation: {
        isGenerating: true,
        progress: [
          { type: "progress", section: "Fondations", index: 0, total: 5, status: "done" },
          { type: "progress", section: "Élévation", index: 1, total: 5, status: "done" },
        ],
      },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Élévation")).toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — juste généré (SSE, avant refetch)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("generation.generatedData non nul affiche le contenu du résumé généré", () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "done" } },
      generation: { generatedData: cachedSummary },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Fondations")).toBeInTheDocument();
  });

  it('generation.finalStatus "partial" affiche la bannière résumé partiel', () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "done" } },
      generation: { generatedData: cachedSummary, finalStatus: "partial" },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(
      screen.getByText(/Certaines sections n'ont pas pu être extraites/),
    ).toBeInTheDocument();
  });

  it('generation.finalStatus différent de "partial" n\'affiche pas la bannière partielle', () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "done" } },
      generation: { generatedData: cachedSummary, finalStatus: "done" },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(
      screen.queryByText(/Certaines sections n'ont pas pu être extraites/),
    ).not.toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — résumé en cache, cas additionnels", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('summary.data.status "partial" affiche la bannière résumé partiel', () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: true, status: "partial" } },
      summary: {
        data: {
          id: "s-1",
          project_id: "p-1",
          status: "partial",
          data: cachedSummary,
          error_message: null,
          generated_at: "2026-09-01T00:00:00Z",
        },
      },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(
      screen.getByText(/Certaines sections n'ont pas pu être extraites/),
    ).toBeInTheDocument();
  });

  it('summary.data.status "error" affiche La génération a échoué suivi de error_message', () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: true, status: "error" } },
      summary: {
        data: {
          id: "s-1",
          project_id: "p-1",
          status: "error",
          data: cachedSummary,
          error_message: "Quota dépassé.",
          generated_at: "2026-09-01T00:00:00Z",
        },
      },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText(/La génération a échoué\..*Quota dépassé\./)).toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — prêt à générer / erreur de génération", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("aucune donnée, generation.error non nul affiche le message et le bouton Réessayer", () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "none" } },
      generation: { error: "Le service est indisponible." },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Le service est indisponible.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Réessayer/ })).toBeInTheDocument();
  });

  it("aucune donnée, generation.error nul affiche l'invitation Générer le résumé", () => {
    armHooks({
      status: { data: { has_documents: true, has_summary: false, status: "none" } },
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Résumé IA disponible")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Générer le résumé/ })).toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — affichage du contenu", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  function armWithData(data: ProjectSummaryData): void {
    armHooks({
      status: { data: { has_documents: true, has_summary: true, status: "done" } },
      summary: {
        data: {
          id: "s-1",
          project_id: "p-1",
          status: "done",
          data,
          error_message: null,
          generated_at: "2026-09-01T00:00:00Z",
        },
      },
    });
  }

  it("affiche la description du projet et le nom du projet", () => {
    armWithData(cachedSummary);

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Bâtiment R+2 en zone urbaine")).toBeInTheDocument();
    expect(screen.getByText("Groupe scolaire")).toBeInTheDocument();
  });

  it("affiche chaque entrée du système constructif avec son icône/numéro, ses badges KPI et ses détails", () => {
    armWithData(cachedSummary);

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Fondations")).toBeInTheDocument();
    expect(screen.getByText("Profondeur 0,80 m")).toBeInTheDocument();
    expect(screen.getByText("Béton C25/30")).toBeInTheDocument();
  });

  it("n'affiche pas la section Système constructif quand systemeConstructif est vide", () => {
    armWithData({ ...cachedSummary, systemeConstructif: [] });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.queryByText("Système constructif")).not.toBeInTheDocument();
  });

  it("affiche chaque contrainte avec son icône, ses badges KPI et ses détails", () => {
    armWithData({
      ...cachedSummary,
      contraintes: [
        {
          label: "Sismique",
          kpis: ["Zone 3"],
          details: ["Chaînage renforcé"],
        },
      ],
    });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Sismique")).toBeInTheDocument();
    expect(screen.getByText("Zone 3")).toBeInTheDocument();
    expect(screen.getByText("Chaînage renforcé")).toBeInTheDocument();
  });

  it("n'affiche pas la section Contraintes quand contraintes est vide", () => {
    armWithData({ ...cachedSummary, contraintes: [] });

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(
      screen.queryByText("Contraintes techniques & réglementaires"),
    ).not.toBeInTheDocument();
  });
});

describe("ProjectSummaryTab — a regeneration that failed on a project already summarised", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("tells the user the regeneration failed instead of silently showing the old summary", () => {
    armCachedSummary("Erreur lors de la génération du résumé.");

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Erreur lors de la génération du résumé.");
    expect(alert).toHaveTextContent("Le résumé affiché est le précédent");
  });

  it("keeps the previous summary on screen alongside the failure", () => {
    armCachedSummary("Erreur lors de la génération du résumé.");

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.getByText("Fondations")).toBeInTheDocument();
  });

  it("shows no alert when the regeneration did not fail", () => {
    armCachedSummary(null);

    render(<ProjectSummaryTab projectId="p-1" projectName="Groupe scolaire" />);

    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Fondations")).toBeInTheDocument();
  });
});
