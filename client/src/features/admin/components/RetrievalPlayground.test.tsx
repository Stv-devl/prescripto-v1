import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { err, ok } from "@/lib/result";
import { renderWithProviders } from "@/test/utils";
import * as adminService from "../services/admin.service";
import { playgroundResults, stats } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { RetrievalPlayground } from "./RetrievalPlayground";

vi.mock("../services/admin.service");

async function search(): Promise<void> {
  await userEvent.type(screen.getByRole("textbox"), "épaisseur isolation");
  await userEvent.click(screen.getByRole("button", { name: /Rechercher/ }));
}

describe("RetrievalPlayground — a failed search leaves a trace on screen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
  });

  it("renders the failure where the results would have appeared when the search failed", async () => {
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      err({ code: "server_error", message: "playground search failed" }),
    );
    renderWithProviders(
      <RetrievalPlayground projectId="p-1" stats={stats} />,
    );

    await search();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });

  it("renders the results when the search succeeded", async () => {
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      ok(playgroundResults),
    );
    renderWithProviders(
      <RetrievalPlayground projectId="p-1" stats={stats} />,
    );

    await search();

    expect(await screen.findByText(/1 résultats/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("RetrievalPlayground — rendu d'un résultat", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(ok(playgroundResults));
  });

  it("affiche le nom de fichier, la page, la position et le nombre de caractères d'un résultat", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    expect(await screen.findByText("CCTP-lot-3.pdf")).toBeInTheDocument();
    expect(screen.getByText("p.4")).toBeInTheDocument();
    expect(screen.getByText("pos.12")).toBeInTheDocument();
    expect(screen.getByText("820 chars")).toBeInTheDocument();
  });

  it("affiche le pourcentage de similarité et le badge de score qualité", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    expect(await screen.findByText("88% sim")).toBeInTheDocument();
    expect(screen.getByText("Q 82%")).toBeInTheDocument();
  });

  it("affiche le badge de lot quand lot est renseigné", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    const card = (await screen.findByText("CCTP-lot-3.pdf")).closest("article")!;
    expect(within(card).getByText("03")).toBeInTheDocument();
  });

  it("affiche le badge de type de contenu quand content_type est renseigné", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    const card = (await screen.findByText("CCTP-lot-3.pdf")).closest("article")!;
    expect(within(card).getByText("specification")).toBeInTheDocument();
  });

  it("n'affiche aucun badge de type de contenu quand content_type est null", async () => {
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      ok({
        ...playgroundResults,
        results: [{ ...playgroundResults.results[0], content_type: null }],
      }),
    );
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    const card = (await screen.findByText("CCTP-lot-3.pdf")).closest("article")!;
    expect(within(card).queryByText("specification")).not.toBeInTheDocument();
  });

  it("affiche les mots-clés quand keywords est non vide", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    expect(await screen.findByText("isolation")).toBeInTheDocument();
  });

  it("n'affiche aucun mot-clé quand keywords est vide", async () => {
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      ok({
        ...playgroundResults,
        results: [{ ...playgroundResults.results[0], keywords: [] }],
      }),
    );
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    await screen.findByText("CCTP-lot-3.pdf");
    expect(screen.queryByText("isolation")).not.toBeInTheDocument();
  });

  it("affiche l'aperçu du texte", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    expect(
      await screen.findByText("Isolation thermique des murs extérieurs"),
    ).toBeInTheDocument();
  });
});

describe("RetrievalPlayground — expand / collapse", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      ok({
        ...playgroundResults,
        results: [{ ...playgroundResults.results[0], text: "Texte intégral complet du chunk." }],
      }),
    );
  });

  it("cliquer sur Voir le texte complet affiche le texte intégral et change le libellé en Réduire", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);
    await search();
    await screen.findByText("CCTP-lot-3.pdf");

    await user.click(screen.getByRole("button", { name: /Voir le texte complet/ }));

    expect(screen.getByText("Texte intégral complet du chunk.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Réduire/ })).toBeInTheDocument();
  });

  it("cliquer sur Réduire masque le texte intégral", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);
    await search();
    await screen.findByText("CCTP-lot-3.pdf");
    await user.click(screen.getByRole("button", { name: /Voir le texte complet/ }));

    await user.click(screen.getByRole("button", { name: /Réduire/ }));

    expect(screen.queryByText("Texte intégral complet du chunk.")).not.toBeInTheDocument();
  });
});

describe("RetrievalPlayground — navigation", () => {
  it("cliquer sur Voir le détail appelle selectChunk avec l'id du chunk et bascule l'onglet actif sur table", async () => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(ok(playgroundResults));
    const user = userEvent.setup();
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);
    await search();
    await screen.findByText("CCTP-lot-3.pdf");

    await user.click(screen.getByRole("button", { name: "Voir le détail" }));

    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-1");
    expect(useAdminStore.getState().activeTab).toBe("table");
  });
});

describe("RetrievalPlayground — formulaire de recherche", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(ok(playgroundResults));
  });

  it("sélectionner un lot puis lancer une recherche appelle la mutation avec lot renseigné", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await user.selectOptions(screen.getByLabelText("Lot"), "03");
    await search();

    expect(adminService.playgroundSearch).toHaveBeenCalledWith(
      "p-1",
      expect.objectContaining({ lot: "03" }),
    );
  });

  it("sélectionner un content_type puis lancer une recherche appelle la mutation avec content_type renseigné", async () => {
    const user = userEvent.setup();
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await user.selectOptions(screen.getByLabelText("Content type"), "specification");
    await search();

    expect(adminService.playgroundSearch).toHaveBeenCalledWith(
      "p-1",
      expect.objectContaining({ content_type: "specification" }),
    );
  });

  it("appuyer sur Entrée (sans Maj) dans le champ de recherche lance la recherche", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await userEvent.type(screen.getByRole("textbox"), "épaisseur isolation{Enter}");

    expect(adminService.playgroundSearch).toHaveBeenCalled();
  });

  it("appuyer sur Maj+Entrée ne lance pas la recherche", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await userEvent.type(
      screen.getByRole("textbox"),
      "épaisseur isolation{Shift>}{Enter}{/Shift}",
    );

    expect(adminService.playgroundSearch).not.toHaveBeenCalled();
  });

  it("le bouton Rechercher est désactivé quand le champ de recherche est vide", () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    expect(screen.getByRole("button", { name: /Rechercher/ })).toBeDisabled();
  });

  it("appuyer sur Entrée dans un champ de recherche vide ne déclenche pas la mutation", async () => {
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

    expect(adminService.playgroundSearch).not.toHaveBeenCalled();
  });
});

describe("RetrievalPlayground — aucun résultat", () => {
  it("une recherche réussie avec zéro résultat affiche le message Aucun chunk trouvé pour cette requête", async () => {
    vi.resetAllMocks();
    useAdminStore.getState().reset();
    vi.mocked(adminService.playgroundSearch).mockResolvedValue(
      ok({ results: [], query_time_ms: 12, total_results: 0 }),
    );
    renderWithProviders(<RetrievalPlayground projectId="p-1" stats={stats} />);

    await search();

    expect(
      await screen.findByText(/Aucun chunk trouvé pour cette requête/),
    ).toBeInTheDocument();
  });
});
