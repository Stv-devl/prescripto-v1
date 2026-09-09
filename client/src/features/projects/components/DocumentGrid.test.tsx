import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Document, Folder } from "../types/types";
import { DocumentGrid } from "./DocumentGrid";

const readyDoc: Document = {
  id: "doc-1",
  project_id: "p-1",
  folder_id: null,
  filename: "CCTP-lot-3.pdf",
  type: "cctp",
  lot: "03",
  phase: "execution",
  size: 128_000,
  status: "ready",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const processingDoc: Document = {
  id: "doc-2",
  project_id: "p-1",
  folder_id: null,
  filename: "plan-masse.png",
  type: "plan",
  lot: "04",
  phase: "execution",
  size: 64_000,
  status: "processing",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const folderLot3: Folder = {
  id: "folder-1",
  project_id: "p-1",
  name: "Lot 3",
  lot: "03",
  phase: "execution",
  document_count: 2,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const folderLot4: Folder = {
  id: "folder-2",
  project_id: "p-1",
  name: "Lot 4",
  lot: "04",
  phase: "execution",
  document_count: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function baseProps() {
  return {
    documents: [readyDoc],
    onDelete: vi.fn(),
    isDeleting: false,
  };
}

function internalDrag() {
  return { dataTransfer: { types: [], getData: () => "doc-1" } };
}

function externalFileDrag() {
  return { dataTransfer: { types: ["Files"], getData: () => "" } };
}

describe("DocumentGrid — rendu de base", () => {
  it("affiche une carte par document avec son nom de fichier", () => {
    render(<DocumentGrid {...baseProps()} documents={[readyDoc, processingDoc]} />);

    expect(screen.getByText(readyDoc.filename)).toBeInTheDocument();
    expect(screen.getByText(processingDoc.filename)).toBeInTheDocument();
  });

  it("affiche une carte par dossier avec son nom et son compteur de documents, avant les cartes document", () => {
    const { container } = render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} />,
    );

    const articles = container.querySelectorAll("article");
    expect(articles[0]).toHaveTextContent("Lot 3");
    expect(articles[0]).toHaveTextContent("2");
    expect(articles[1]).toHaveTextContent(readyDoc.filename);
  });

  it("affiche l'icône de type de fichier correspondant à l'extension", () => {
    render(<DocumentGrid {...baseProps()} documents={[readyDoc, processingDoc]} />);

    const pdfCard = screen.getByText(readyDoc.filename).closest("article")!;
    const pngCard = screen.getByText(processingDoc.filename).closest("article")!;
    expect(pdfCard.querySelector("svg.text-red-400")).toBeTruthy();
    expect(pngCard.querySelector("svg.text-purple-400")).toBeTruthy();
  });
});

describe("DocumentGrid — sélection", () => {
  it("cliquer sur la case d'une carte document appelle onToggleSelect avec son id", async () => {
    const user = userEvent.setup();
    const onToggleSelect = vi.fn();
    render(
      <DocumentGrid
        {...baseProps()}
        selectedIds={new Set()}
        onToggleSelect={onToggleSelect}
      />,
    );

    await user.click(
      screen.getByRole("checkbox", { name: `Sélectionner ${readyDoc.filename}` }),
    );

    expect(onToggleSelect).toHaveBeenCalledWith(readyDoc.id);
  });

  it("sans selectedIds/onToggleSelect, aucune case à cocher n'est rendue", () => {
    render(<DocumentGrid {...baseProps()} />);

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("DocumentGrid — actions document", () => {
  it("cliquer sur Supprimer d'une carte document appelle onDelete avec ce document", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<DocumentGrid {...baseProps()} onDelete={onDelete} />);

    await user.click(
      screen.getByRole("button", { name: `Supprimer ${readyDoc.filename}` }),
    );

    expect(onDelete).toHaveBeenCalledWith(readyDoc);
  });

  it("le bouton supprimer est désactivé quand isDeleting est vrai", () => {
    render(<DocumentGrid {...baseProps()} isDeleting />);

    expect(
      screen.getByRole("button", { name: `Supprimer ${readyDoc.filename}` }),
    ).toBeDisabled();
  });

  it("un document en statut processing affiche la barre de progression, pas le badge de statut", () => {
    render(<DocumentGrid {...baseProps()} documents={[processingDoc]} />);

    expect(screen.queryByText("Prêt")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Extraction…|Nettoyage…|Classification…|Découpage…|Indexation…/),
    ).toBeInTheDocument();
  });

  it("un document en statut ready affiche le badge de statut, pas la barre de progression", () => {
    render(<DocumentGrid {...baseProps()} documents={[readyDoc]} />);

    expect(screen.getByText("Prêt")).toBeInTheDocument();
  });

  it("cliquer sur une carte document appelle onDocumentClick avec ce document", async () => {
    const user = userEvent.setup();
    const onDocumentClick = vi.fn();
    render(<DocumentGrid {...baseProps()} onDocumentClick={onDocumentClick} />);

    await user.click(screen.getByText(readyDoc.filename));

    expect(onDocumentClick).toHaveBeenCalledWith(readyDoc);
  });
});

describe("DocumentGrid — actions dossier", () => {
  it("cliquer sur Renommer un dossier affiche InlineFolderRename pour ce dossier précisément (pas les autres)", async () => {
    const user = userEvent.setup();
    render(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3, folderLot4]}
        onRenameFolder={vi.fn()}
      />,
    );

    await user.click(
      screen.getAllByRole("button", { name: "Renommer le dossier" })[0],
    );

    expect(screen.getByRole("textbox")).toHaveValue("Lot 3");
    expect(screen.queryByDisplayValue("Lot 4")).not.toBeInTheDocument();
  });

  it("cliquer sur Supprimer un dossier appelle onDeleteFolder avec ce dossier", async () => {
    const user = userEvent.setup();
    const onDeleteFolder = vi.fn();
    render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} onDeleteFolder={onDeleteFolder} />,
    );

    await user.click(screen.getByRole("button", { name: "Supprimer le dossier" }));

    expect(onDeleteFolder).toHaveBeenCalledWith(folderLot3);
  });

  it("cliquer sur une carte dossier (hors édition) appelle onOpenFolder avec son id", async () => {
    const user = userEvent.setup();
    const onOpenFolder = vi.fn();
    render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} onOpenFolder={onOpenFolder} />,
    );

    await user.click(screen.getByText("Lot 3"));

    expect(onOpenFolder).toHaveBeenCalledWith(folderLot3.id);
  });

  it("cliquer sur une carte dossier en cours de renommage n'appelle PAS onOpenFolder", async () => {
    const user = userEvent.setup();
    const onOpenFolder = vi.fn();
    render(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3]}
        onOpenFolder={onOpenFolder}
        onRenameFolder={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));
    fireEvent.click(screen.getByRole("textbox").closest("article")!);

    expect(onOpenFolder).not.toHaveBeenCalled();
  });

  it("sans onRenameFolder, le bouton Renommer le dossier n'est pas rendu", () => {
    render(<DocumentGrid {...baseProps()} folders={[folderLot3]} />);

    expect(
      screen.queryByRole("button", { name: "Renommer le dossier" }),
    ).not.toBeInTheDocument();
  });

  it("sans onDeleteFolder, le bouton Supprimer le dossier n'est pas rendu", () => {
    render(<DocumentGrid {...baseProps()} folders={[folderLot3]} />);

    expect(
      screen.queryByRole("button", { name: "Supprimer le dossier" }),
    ).not.toBeInTheDocument();
  });

  it("pendant qu'un dossier est en cours de renommage, un autre dossier perd lui aussi ses boutons renommer/supprimer", async () => {
    const user = userEvent.setup();
    render(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3, folderLot4]}
        onRenameFolder={vi.fn()}
        onDeleteFolder={vi.fn()}
      />,
    );

    await user.click(
      screen.getAllByRole("button", { name: "Renommer le dossier" })[0],
    );

    expect(
      screen.queryByRole("button", { name: "Renommer le dossier" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Supprimer le dossier" }),
    ).not.toBeInTheDocument();
  });
});

describe("DocumentGrid — état d'édition contrôlé / non contrôlé", () => {
  it("mode contrôlé : cliquer sur Renommer appelle onEditingFolderIdChange avec l'id du dossier", async () => {
    const user = userEvent.setup();
    const onEditingFolderIdChange = vi.fn();
    render(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3]}
        onRenameFolder={vi.fn()}
        editingFolderIdExternal={null}
        onEditingFolderIdChange={onEditingFolderIdChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));

    expect(onEditingFolderIdChange).toHaveBeenCalledWith(folderLot3.id);
  });

  it("mode non contrôlé : cliquer sur Renommer affiche InlineFolderRename via l'état interne seul", async () => {
    const user = userEvent.setup();
    render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} onRenameFolder={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));

    expect(screen.getByRole("textbox")).toHaveValue("Lot 3");
  });

  it("annuler un renommage en mode contrôlé appelle onEditingFolderIdChange avec null", async () => {
    const user = userEvent.setup();
    const onEditingFolderIdChange = vi.fn();
    const { rerender } = render(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3]}
        onRenameFolder={vi.fn()}
        editingFolderIdExternal={null}
        onEditingFolderIdChange={onEditingFolderIdChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));
    rerender(
      <DocumentGrid
        {...baseProps()}
        folders={[folderLot3]}
        onRenameFolder={vi.fn()}
        editingFolderIdExternal={folderLot3.id}
        onEditingFolderIdChange={onEditingFolderIdChange}
      />,
    );

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });

    expect(onEditingFolderIdChange).toHaveBeenCalledWith(null);
  });
});

describe("DocumentGrid — navigation racine", () => {
  it("la carte Racine n'apparaît que si currentFolderId est renseigné ET onMoveDocument est fourni", () => {
    const { rerender } = render(<DocumentGrid {...baseProps()} />);
    expect(screen.queryByText("Racine")).not.toBeInTheDocument();

    rerender(
      <DocumentGrid {...baseProps()} currentFolderId="folder-1" onMoveDocument={vi.fn()} />,
    );
    expect(screen.getByText("Racine")).toBeInTheDocument();
  });
});

describe("DocumentGrid — menu contextuel", () => {
  it("clic droit sur une carte document appelle onContextMenu avec { type: 'document', item: doc }", () => {
    const onContextMenu = vi.fn();
    render(<DocumentGrid {...baseProps()} onContextMenu={onContextMenu} />);

    fireEvent.contextMenu(screen.getByText(readyDoc.filename));

    expect(onContextMenu).toHaveBeenCalledWith(expect.anything(), {
      type: "document",
      item: readyDoc,
    });
  });

  it("clic droit sur une carte dossier appelle onContextMenu avec { type: 'folder', item: folder }", () => {
    const onContextMenu = vi.fn();
    render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} onContextMenu={onContextMenu} />,
    );

    fireEvent.contextMenu(screen.getByText("Lot 3"));

    expect(onContextMenu).toHaveBeenCalledWith(expect.anything(), {
      type: "folder",
      item: folderLot3,
    });
  });
});

describe("DocumentGrid — drag-and-drop", () => {
  it("survoler une carte dossier avec un drag interne affiche Déposer ici", () => {
    render(<DocumentGrid {...baseProps()} folders={[folderLot3]} onMoveDocument={vi.fn()} />);

    fireEvent.dragOver(screen.getByText("Lot 3").closest("article")!, internalDrag());

    expect(screen.getByText("Déposer ici")).toBeInTheDocument();
  });

  it("survoler une carte dossier avec un drag externe de fichier affiche Ajouter au dossier, pas Déposer ici", () => {
    render(<DocumentGrid {...baseProps()} folders={[folderLot3]} onMoveDocument={vi.fn()} />);

    fireEvent.dragOver(screen.getByText("Lot 3").closest("article")!, externalFileDrag());

    expect(screen.getByText("Ajouter au dossier")).toBeInTheDocument();
    expect(screen.queryByText("Déposer ici")).not.toBeInTheDocument();
  });

  it("démarrer un drag depuis une carte document puis le relâcher sans dépôt valide n'appelle ni onMoveDocument ni onDelete", () => {
    const onMoveDocument = vi.fn();
    const onDelete = vi.fn();
    render(
      <DocumentGrid
        {...baseProps()}
        onDelete={onDelete}
        onMoveDocument={onMoveDocument}
      />,
    );
    const card = screen.getByText(readyDoc.filename).closest("article")!;

    fireEvent.dragStart(card, {
      dataTransfer: { setData: vi.fn(), setDragImage: vi.fn(), effectAllowed: "" },
    });
    fireEvent.dragEnd(card);

    expect(onMoveDocument).not.toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("déposer un document glissé sur une carte dossier appelle onMoveDocument avec l'id du document et l'id du dossier cible", () => {
    const onMoveDocument = vi.fn();
    render(
      <DocumentGrid {...baseProps()} folders={[folderLot3]} onMoveDocument={onMoveDocument} />,
    );

    fireEvent.drop(screen.getByText("Lot 3").closest("article")!, internalDrag());

    expect(onMoveDocument).toHaveBeenCalledWith("doc-1", folderLot3.id);
  });

  it("déposer un document glissé sur la carte Racine appelle onMoveDocument avec l'id du document et null", () => {
    const onMoveDocument = vi.fn();
    render(
      <DocumentGrid
        {...baseProps()}
        currentFolderId="folder-1"
        onMoveDocument={onMoveDocument}
      />,
    );

    fireEvent.drop(screen.getByText("Racine").closest("article")!, internalDrag());

    expect(onMoveDocument).toHaveBeenCalledWith("doc-1", null);
  });

  it("déposer un fichier externe sur le conteneur appelle onFileDrop", () => {
    const onFileDrop = vi.fn();
    const { container } = render(
      <DocumentGrid {...baseProps()} onFileDrop={onFileDrop} />,
    );

    fireEvent.drop(container.firstChild as Element, externalFileDrag());

    expect(onFileDrop).toHaveBeenCalled();
  });
});
