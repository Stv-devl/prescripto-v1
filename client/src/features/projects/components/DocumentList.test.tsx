import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Document, Folder } from "../types/types";
import { DocumentList } from "./DocumentList";

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
  filename: "plan.png",
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
    sortField: "filename" as const,
    sortDirection: "asc" as const,
    onSort: vi.fn(),
  };
}

describe("DocumentList — rendu de base", () => {
  it("affiche une ligne par document avec son nom de fichier", () => {
    render(
      <table>
        <DocumentList {...baseProps()} documents={[readyDoc, processingDoc]} />
      </table>,
    );

    expect(screen.getByText(readyDoc.filename)).toBeInTheDocument();
    expect(screen.getByText(processingDoc.filename)).toBeInTheDocument();
  });

  it("affiche une ligne par dossier avec son nom et son compteur de documents, avant les lignes document", () => {
    render(
      <table>
        <DocumentList
          {...baseProps()}
          documents={[readyDoc]}
          folders={[folderLot3]}
        />
      </table>,
    );

    const rows = screen.getAllByRole("row");
    // rows[0] is the header row
    expect(within(rows[1]).getByText("Lot 3")).toBeInTheDocument();
    expect(within(rows[1]).getByText(/2 docs/)).toBeInTheDocument();
    expect(within(rows[2]).getByText(readyDoc.filename)).toBeInTheDocument();
  });

  it("affiche l'icône de type de fichier correspondant à l'extension", () => {
    render(
      <table>
        <DocumentList {...baseProps()} documents={[readyDoc, processingDoc]} />
      </table>,
    );

    const pdfRow = screen.getByText(readyDoc.filename).closest("tr")!;
    const pngRow = screen.getByText(processingDoc.filename).closest("tr")!;
    expect(pdfRow.querySelector("svg.text-red-400")).toBeTruthy();
    expect(pngRow.querySelector("svg.text-purple-400")).toBeTruthy();
  });
});

describe("DocumentList — tri", () => {
  it('cliquer sur l\'en-tête "Fichier" appelle onSort("filename")', async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(
      <table>
        <DocumentList {...baseProps()} onSort={onSort} />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: /Fichier/ }));

    expect(onSort).toHaveBeenCalledWith("filename");
  });

  it("la colonne triée active affiche le chevron dans la direction de sortDirection", () => {
    render(
      <table>
        <DocumentList {...baseProps()} sortField="filename" sortDirection="desc" />
      </table>,
    );

    const header = screen.getByRole("button", { name: /Fichier/ });
    expect(header.querySelector("svg.lucide-chevron-down")).toBeTruthy();
    expect(header.querySelector("svg.opacity-30")).toBeFalsy();
  });
});

describe("DocumentList — sélection", () => {
  it('la case "tout sélectionner" est cochée quand tous les documents visibles sont dans selectedIds', () => {
    render(
      <table>
        <DocumentList
          {...baseProps()}
          documents={[readyDoc, processingDoc]}
          selectedIds={new Set([readyDoc.id, processingDoc.id])}
          onToggleSelect={vi.fn()}
          onToggleSelectAll={vi.fn()}
        />
      </table>,
    );

    expect(
      screen.getByRole("checkbox", { name: "Tout sélectionner" }),
    ).toBeChecked();
  });

  it('la case "tout sélectionner" est en état indéterminé quand une partie seulement des documents est sélectionnée', () => {
    render(
      <table>
        <DocumentList
          {...baseProps()}
          documents={[readyDoc, processingDoc]}
          selectedIds={new Set([readyDoc.id])}
          onToggleSelect={vi.fn()}
          onToggleSelectAll={vi.fn()}
        />
      </table>,
    );

    const selectAll = screen.getByRole("checkbox", {
      name: "Tout sélectionner",
    }) as HTMLInputElement;
    expect(selectAll.checked).toBe(false);
    expect(selectAll.indeterminate).toBe(true);
  });

  it("cliquer sur la case d'un document appelle onToggleSelect avec son id", async () => {
    const user = userEvent.setup();
    const onToggleSelect = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          selectedIds={new Set()}
          onToggleSelect={onToggleSelect}
          onToggleSelectAll={vi.fn()}
        />
      </table>,
    );

    await user.click(
      screen.getByRole("checkbox", { name: `Sélectionner ${readyDoc.filename}` }),
    );

    expect(onToggleSelect).toHaveBeenCalledWith(readyDoc.id);
  });

  it("cliquer sur la case tout sélectionner appelle onToggleSelectAll avec tous les ids de documents", async () => {
    const user = userEvent.setup();
    const onToggleSelectAll = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          documents={[readyDoc, processingDoc]}
          selectedIds={new Set()}
          onToggleSelect={vi.fn()}
          onToggleSelectAll={onToggleSelectAll}
        />
      </table>,
    );

    await user.click(screen.getByRole("checkbox", { name: "Tout sélectionner" }));

    expect(onToggleSelectAll).toHaveBeenCalledWith([readyDoc.id, processingDoc.id]);
  });

  it("sans selectedIds/onToggleSelect, aucune case à cocher n'est rendue", () => {
    render(
      <table>
        <DocumentList {...baseProps()} />
      </table>,
    );

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("DocumentList — actions document", () => {
  it("cliquer sur Supprimer d'un document appelle onDelete avec ce document", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <table>
        <DocumentList {...baseProps()} onDelete={onDelete} />
      </table>,
    );

    await user.click(
      screen.getByRole("button", { name: `Supprimer ${readyDoc.filename}` }),
    );

    expect(onDelete).toHaveBeenCalledWith(readyDoc);
  });

  it("le bouton supprimer est désactivé quand isDeleting est vrai", () => {
    render(
      <table>
        <DocumentList {...baseProps()} isDeleting />
      </table>,
    );

    expect(
      screen.getByRole("button", { name: `Supprimer ${readyDoc.filename}` }),
    ).toBeDisabled();
  });

  it("un document en statut processing affiche la barre de progression, pas le badge de statut", () => {
    render(
      <table>
        <DocumentList {...baseProps()} documents={[processingDoc]} />
      </table>,
    );

    expect(screen.queryByText("Prêt")).not.toBeInTheDocument();
    expect(screen.queryByText("Traitement…")).not.toBeInTheDocument();
    expect(screen.getByText(/Extraction…|Nettoyage…|Classification…|Découpage…|Indexation…/)).toBeInTheDocument();
  });

  it("un document en statut ready affiche le badge de statut, pas la barre de progression", () => {
    render(
      <table>
        <DocumentList {...baseProps()} documents={[readyDoc]} />
      </table>,
    );

    expect(screen.getByText("Prêt")).toBeInTheDocument();
  });

  it("cliquer sur une ligne document appelle onDocumentClick avec ce document", async () => {
    const user = userEvent.setup();
    const onDocumentClick = vi.fn();
    render(
      <table>
        <DocumentList {...baseProps()} onDocumentClick={onDocumentClick} />
      </table>,
    );

    await user.click(screen.getByText(readyDoc.filename));

    expect(onDocumentClick).toHaveBeenCalledWith(readyDoc);
  });
});

describe("DocumentList — actions dossier", () => {
  it("cliquer sur Renommer un dossier affiche InlineFolderRename pour ce dossier précisément (pas les autres)", async () => {
    const user = userEvent.setup();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3, folderLot4]}
          onRenameFolder={vi.fn()}
          isRenamingFolder={false}
        />
      </table>,
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
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onDeleteFolder={onDeleteFolder}
        />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: "Supprimer le dossier" }));

    expect(onDeleteFolder).toHaveBeenCalledWith(folderLot3);
  });

  it("cliquer sur une ligne dossier (hors édition) appelle onOpenFolder avec son id", async () => {
    const user = userEvent.setup();
    const onOpenFolder = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onOpenFolder={onOpenFolder}
        />
      </table>,
    );

    await user.click(screen.getByText("Lot 3"));

    expect(onOpenFolder).toHaveBeenCalledWith(folderLot3.id);
  });

  it("cliquer sur une ligne dossier en cours de renommage n'appelle PAS onOpenFolder", async () => {
    const user = userEvent.setup();
    const onOpenFolder = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onOpenFolder={onOpenFolder}
          onRenameFolder={vi.fn()}
        />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));
    // A real click elsewhere blurs the still-focused rename input first,
    // which itself cancels rename mode (InlineFolderRename's onBlur calls
    // handleSubmit -> onCancel) before the row's own onClick evaluates —
    // so this exercises the guard directly, on the un-blurred tr element,
    // the way the guard's code (not the blur side effect) is meant to be proven.
    fireEvent.click(screen.getByRole("textbox").closest("tr")!);

    expect(onOpenFolder).not.toHaveBeenCalled();
  });

  it("sans onRenameFolder, le bouton Renommer le dossier n'est pas rendu", () => {
    render(
      <table>
        <DocumentList {...baseProps()} folders={[folderLot3]} />
      </table>,
    );

    expect(
      screen.queryByRole("button", { name: "Renommer le dossier" }),
    ).not.toBeInTheDocument();
  });

  it("sans onDeleteFolder, le bouton Supprimer le dossier n'est pas rendu", () => {
    render(
      <table>
        <DocumentList {...baseProps()} folders={[folderLot3]} />
      </table>,
    );

    expect(
      screen.queryByRole("button", { name: "Supprimer le dossier" }),
    ).not.toBeInTheDocument();
  });
});

describe("DocumentList — état d'édition contrôlé / non contrôlé", () => {
  it("mode contrôlé : cliquer sur Renommer appelle onEditingFolderIdChange avec l'id du dossier", async () => {
    const user = userEvent.setup();
    const onEditingFolderIdChange = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onRenameFolder={vi.fn()}
          editingFolderIdExternal={null}
          onEditingFolderIdChange={onEditingFolderIdChange}
        />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));

    expect(onEditingFolderIdChange).toHaveBeenCalledWith(folderLot3.id);
  });

  it("mode non contrôlé : cliquer sur Renommer affiche InlineFolderRename via l'état interne seul", async () => {
    const user = userEvent.setup();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onRenameFolder={vi.fn()}
        />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));

    expect(screen.getByRole("textbox")).toHaveValue("Lot 3");
  });

  it("annuler un renommage en mode contrôlé appelle onEditingFolderIdChange avec null", async () => {
    const user = userEvent.setup();
    const onEditingFolderIdChange = vi.fn();
    const { rerender } = render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onRenameFolder={vi.fn()}
          editingFolderIdExternal={null}
          onEditingFolderIdChange={onEditingFolderIdChange}
        />
      </table>,
    );

    await user.click(screen.getByRole("button", { name: "Renommer le dossier" }));
    rerender(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onRenameFolder={vi.fn()}
          editingFolderIdExternal={folderLot3.id}
          onEditingFolderIdChange={onEditingFolderIdChange}
        />
      </table>,
    );

    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Escape" });

    expect(onEditingFolderIdChange).toHaveBeenCalledWith(null);
  });
});

describe("DocumentList — navigation racine", () => {
  it("la ligne Déplacer vers la racine n'apparaît que si currentFolderId est renseigné ET onMoveDocument est fourni", () => {
    const { rerender } = render(
      <table>
        <DocumentList {...baseProps()} />
      </table>,
    );
    expect(screen.queryByText("Déplacer vers la racine")).not.toBeInTheDocument();

    rerender(
      <table>
        <DocumentList
          {...baseProps()}
          currentFolderId="folder-1"
          onMoveDocument={vi.fn()}
        />
      </table>,
    );
    expect(screen.getByText("Déplacer vers la racine")).toBeInTheDocument();
  });
});

describe("DocumentList — menu contextuel", () => {
  it("clic droit sur une ligne document appelle onContextMenu avec { type: 'document', item: doc }", () => {
    const onContextMenu = vi.fn();
    render(
      <table>
        <DocumentList {...baseProps()} onContextMenu={onContextMenu} />
      </table>,
    );

    fireEvent.contextMenu(screen.getByText(readyDoc.filename));

    expect(onContextMenu).toHaveBeenCalledWith(
      expect.anything(),
      { type: "document", item: readyDoc },
    );
  });

  it("clic droit sur une ligne dossier appelle onContextMenu avec { type: 'folder', item: folder }", () => {
    const onContextMenu = vi.fn();
    render(
      <table>
        <DocumentList
          {...baseProps()}
          folders={[folderLot3]}
          onContextMenu={onContextMenu}
        />
      </table>,
    );

    fireEvent.contextMenu(screen.getByText("Lot 3"));

    expect(onContextMenu).toHaveBeenCalledWith(
      expect.anything(),
      { type: "folder", item: folderLot3 },
    );
  });
});
