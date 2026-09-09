import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { chunkPage, emptyChunkPage, failureWithCode } from "../testFixtures";
import { useAdminStore } from "../stores/store";
import { ChunkTable } from "./ChunkTable";

const EMPTY_COPY = "Aucun chunk trouvé avec ces filtres.";

describe("ChunkTable — an empty state must never stand in for a failure", () => {
  beforeEach(() => {
    useAdminStore.getState().reset();
  });

  it("renders the failure instead of « Aucun chunk trouvé avec ces filtres » when the request failed with no data", () => {
    render(
      <ChunkTable
        data={undefined}
        isPending={false}
        error={failureWithCode("server_error")}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Le service est momentanément indisponible. Réessayez.",
    );
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });

  it("renders the failure instead of the empty copy when a refetch fails over a cached zero-chunk result", () => {
    render(
      <ChunkTable
        data={emptyChunkPage}
        isPending={false}
        error={failureWithCode("server_error")}
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });

  it("renders the chunk rows when the request returned results", () => {
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);

    expect(screen.getByText("CCTP-lot-3.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders « Aucun chunk trouvé avec ces filtres » when the request returned zero chunks and no error", () => {
    render(<ChunkTable data={emptyChunkPage} isPending={false} error={null} />);

    expect(screen.getByText(EMPTY_COPY)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps the previous table on screen and puts the failure above it when a refetch fails over kept data", () => {
    render(
      <ChunkTable
        data={chunkPage}
        isPending={false}
        error={failureWithCode("network_error")}
      />,
    );

    expect(screen.getByText("CCTP-lot-3.pdf")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Erreur de connexion");
  });

  it("renders the French copy of the error code, never the technical message", () => {
    render(
      <ChunkTable
        data={undefined}
        isPending={false}
        error={failureWithCode("forbidden")}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Accès refusé");
    expect(screen.queryByText(/admin request failed/)).not.toBeInTheDocument();
  });

  it("renders the skeleton alone during the first load — neither the failure nor the empty state", () => {
    render(<ChunkTable data={undefined} isPending={true} error={null} />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(EMPTY_COPY)).not.toBeInTheDocument();
  });
});

describe("ChunkTable — sortable headers", () => {
  beforeEach(() => {
    useAdminStore.getState().reset();
  });

  it("cliquer l'en-tête « Pos » trie toujours par position — régression, identique au comportement actuel", async () => {
    const user = userEvent.setup();
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);

    await user.click(screen.getByRole("button", { name: "Pos" }));

    expect(useAdminStore.getState().filters.sort_by).toBe("position");
    expect(useAdminStore.getState().filters.sort_order).toBe("desc");
  });

  it("appuyer sur Entrée sur le bouton de l'en-tête « Pos » trie par position", async () => {
    const user = userEvent.setup();
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);
    screen.getByRole("button", { name: "Pos" }).focus();

    await user.keyboard("{Enter}");

    expect(useAdminStore.getState().filters.sort_by).toBe("position");
    expect(useAdminStore.getState().filters.sort_order).toBe("desc");
  });

  it("appuyer sur Espace sur le bouton de l'en-tête « Pos » trie par position", async () => {
    const user = userEvent.setup();
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);
    screen.getByRole("button", { name: "Pos" }).focus();

    await user.keyboard(" ");

    expect(useAdminStore.getState().filters.sort_by).toBe("position");
    expect(useAdminStore.getState().filters.sort_order).toBe("desc");
  });

  it("aria-sort de la colonne triée courante vaut ascending ou descending selon l'ordre", async () => {
    const user = userEvent.setup();
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);

    expect(screen.getByRole("columnheader", { name: "Pos" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );

    await user.click(screen.getByRole("button", { name: "Pos" }));

    expect(screen.getByRole("columnheader", { name: "Pos" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("trier une nouvelle colonne remet aria-sort=none sur l'ancienne colonne", async () => {
    const user = userEvent.setup();
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);

    await user.click(screen.getByRole("button", { name: "Page" }));

    expect(screen.getByRole("columnheader", { name: "Pos" })).toHaveAttribute(
      "aria-sort",
      "none",
    );
    expect(screen.getByRole("columnheader", { name: "Page" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
  });

  it("une colonne non triable ne porte aucun attribut aria-sort", () => {
    render(<ChunkTable data={chunkPage} isPending={false} error={null} />);

    expect(
      screen.getByRole("columnheader", { name: "Document" }),
    ).not.toHaveAttribute("aria-sort");
  });
});
