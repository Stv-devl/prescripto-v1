import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/utils";
import { ServiceFailure } from "@/lib/result";
import type { Document, Folder } from "@/features/projects";
import { WorkspaceDocumentsTab } from "./WorkspaceDocumentsTab";

const doc: Document = {
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

const folder: Folder = {
  id: "folder-1",
  project_id: "p-1",
  name: "Lot 3",
  lot: "03",
  phase: "execution",
  document_count: 2,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function baseProps() {
  return {
    projectId: "p-1",
    sortedDocuments: [doc],
    sortField: "created_at" as const,
    sortDirection: "desc" as const,
    onSort: vi.fn(),
    search: "",
    onSearchChange: vi.fn(),
    summary: "1 document — 128 KB",
    currentFolderId: null,
    onOpenFolder: vi.fn(),
    currentFolder: null,
    folderOptions: [folder],
    selectedIds: new Set<string>(),
    onToggleSelect: vi.fn(),
    onToggleSelectAll: vi.fn(),
    onDeleteDocument: vi.fn(),
    onMoveDocument: vi.fn(),
    onDeleteFolder: vi.fn(),
    onRenameFolder: vi.fn(),
    isRenamingFolder: false,
    onShowCreateFolder: vi.fn(),
    externalDragOver: false,
    onSectionDragEnter: vi.fn(),
    onSectionDragOver: vi.fn(),
    onSectionDragLeave: vi.fn(),
    onSectionDrop: vi.fn(),
    onFileDropOnFolder: vi.fn(),
    onContextMenu: vi.fn(),
    editingFolderIdExternal: null,
    onEditingFolderIdChange: vi.fn(),
    isDocsPending: false,
    docsError: null,
    hasDocuments: true,
    hasFolders: false,
  };
}

describe("WorkspaceDocumentsTab — comportement principal", () => {
  it("affiche le spinner pendant isDocsPending", () => {
    const { container } = renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        isDocsPending={true}
        hasDocuments={false}
        hasFolders={false}
      />,
    );

    expect(container.querySelector("svg.animate-spin")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Rechercher…")).not.toBeInTheDocument();
  });

  it("affiche ErrorMessage quand docsError est non nul", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        docsError={new ServiceFailure({ code: "server_error", message: "boom" })}
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("affiche l'état vide global quand ni documents ni dossiers n'existent", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        hasDocuments={false}
        hasFolders={false}
      />,
    );

    expect(
      screen.getByText("Aucun document. Ajoutez un fichier ci-dessus."),
    ).toBeInTheDocument();
  });

  it("bascule entre DocumentList et DocumentGrid selon le clic sur les boutons de vue", async () => {
    renderWithProviders(<WorkspaceDocumentsTab {...baseProps()} />);

    expect(screen.getByRole("table")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Vue grille" }));

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("la recherche appelle onSearchChange à chaque frappe", async () => {
    const onSearchChange = vi.fn();
    renderWithProviders(
      <WorkspaceDocumentsTab {...baseProps()} onSearchChange={onSearchChange} />,
    );

    await userEvent.type(screen.getByPlaceholderText("Rechercher…"), "x");

    expect(onSearchChange).toHaveBeenCalledWith("x");
  });
});

describe("WorkspaceDocumentsTab — règles métier", () => {
  it("n'affiche le bouton Nouveau dossier que hors d'un dossier", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab {...baseProps()} currentFolderId={null} />,
    );
    expect(
      screen.getByRole("button", { name: /Nouveau dossier/ }),
    ).toBeInTheDocument();
  });

  it("cache le bouton Nouveau dossier à l'intérieur d'un dossier", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        currentFolderId="folder-1"
        currentFolder={folder}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /Nouveau dossier/ }),
    ).not.toBeInTheDocument();
  });

  it("affiche le fil d'Ariane uniquement quand currentFolderId et currentFolder sont non nuls", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        currentFolderId="folder-1"
        currentFolder={folder}
        sortedDocuments={[doc]}
      />,
    );

    expect(screen.getByText("Lot 3")).toBeInTheDocument();
    expect(screen.getByText("(1 doc)")).toBeInTheDocument();
  });

  it("accorde le pluriel du fil d'Ariane à plusieurs documents", () => {
    const doc2: Document = { ...doc, id: "doc-2", filename: "b.pdf" };
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        currentFolderId="folder-1"
        currentFolder={folder}
        sortedDocuments={[doc, doc2]}
      />,
    );

    expect(screen.getByText("(2 docs)")).toBeInTheDocument();
  });

  it("ne montre pas le fil d'Ariane hors d'un dossier", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab {...baseProps()} currentFolderId={null} currentFolder={null} />,
    );

    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("dit « dossier vide » à l'intérieur d'un dossier sans document", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        currentFolderId="folder-1"
        currentFolder={folder}
        sortedDocuments={[]}
      />,
    );

    expect(screen.getByText("Ce dossier est vide.")).toBeInTheDocument();
  });

  it("dit « aucun résultat » à la racine sans dossiers ni documents correspondants", () => {
    renderWithProviders(
      <WorkspaceDocumentsTab
        {...baseProps()}
        currentFolderId={null}
        sortedDocuments={[]}
        folderOptions={[]}
      />,
    );

    expect(
      screen.getByText("Aucun document ne correspond à votre recherche."),
    ).toBeInTheDocument();
  });
});

describe("WorkspaceDocumentsTab — cas limites", () => {
  it("applique la surbrillance de glisser-déposer quand externalDragOver est vrai", () => {
    const { container } = renderWithProviders(
      <WorkspaceDocumentsTab {...baseProps()} externalDragOver={true} />,
    );

    expect(container.querySelector("section")).toHaveClass("ring-2");
  });

  it("n'applique aucune surbrillance quand externalDragOver est faux", () => {
    const { container } = renderWithProviders(
      <WorkspaceDocumentsTab {...baseProps()} externalDragOver={false} />,
    );

    expect(container.querySelector("section")).not.toHaveClass("ring-2");
  });
});
