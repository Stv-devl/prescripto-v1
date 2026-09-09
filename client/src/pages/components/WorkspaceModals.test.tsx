import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Document, Folder } from "@/features/projects";
import { WorkspaceModals } from "./WorkspaceModals";

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
    deleteTarget: null,
    onDeleteTargetChange: vi.fn(),
    onConfirmDelete: vi.fn(),
    isDeleting: false,
    showCreateFolder: false,
    onShowCreateFolderChange: vi.fn(),
    onConfirmCreateFolder: vi.fn(),
    isCreatingFolder: false,
    deleteFolderTarget: null,
    onDeleteFolderTargetChange: vi.fn(),
    onConfirmDeleteFolder: vi.fn(),
    isDeletingFolder: false,
    currentFolderId: null,
    onCurrentFolderIdChange: vi.fn(),
    editFolderTarget: null,
    onEditFolderTargetChange: vi.fn(),
    onConfirmEditFolder: vi.fn(),
    isEditingFolder: false,
    previewDoc: null,
    onPreviewDocChange: vi.fn(),
    contextMenu: null,
    onContextMenuClose: vi.fn(),
    onEditingFolderIdChange: vi.fn(),
    selectedIds: new Set<string>(),
    onToggleSelect: vi.fn(),
    selectionCount: 0,
    folders: [folder],
    onMoveSelected: vi.fn(),
    onDeleteSelected: vi.fn(),
    onClearSelection: vi.fn(),
  };
}

describe("WorkspaceModals — comportement principal", () => {
  it("affiche DeleteDocumentModal quand deleteTarget est non nul et confirme la suppression", async () => {
    const onConfirmDelete = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        deleteTarget={doc}
        onConfirmDelete={onConfirmDelete}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Confirmer la suppression du document" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onConfirmDelete).toHaveBeenCalledWith("doc-1");
  });

  it("affiche CreateFolderModal quand showCreateFolder est vrai, confirme puis referme", async () => {
    const onConfirmCreateFolder = vi.fn();
    const onShowCreateFolderChange = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        showCreateFolder={true}
        onConfirmCreateFolder={onConfirmCreateFolder}
        onShowCreateFolderChange={onShowCreateFolderChange}
      />,
    );

    await userEvent.type(screen.getByLabelText(/Nom du dossier/), "Lot 5");
    await userEvent.click(screen.getByRole("button", { name: "Créer" }));

    expect(onConfirmCreateFolder).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Lot 5" }),
    );
    expect(onShowCreateFolderChange).toHaveBeenCalledWith(false);
  });

  it("affiche DeleteFolderModal quand deleteFolderTarget est non nul et confirme la suppression", async () => {
    const onConfirmDeleteFolder = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        deleteFolderTarget={folder}
        onConfirmDeleteFolder={onConfirmDeleteFolder}
      />,
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onConfirmDeleteFolder).toHaveBeenCalledWith("folder-1");
  });

  it("affiche EditFolderModal quand editFolderTarget est non nul et confirme les changements", async () => {
    const onConfirmEditFolder = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        editFolderTarget={folder}
        onConfirmEditFolder={onConfirmEditFolder}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(onConfirmEditFolder).toHaveBeenCalledWith(
      expect.objectContaining({ folderId: "folder-1" }),
    );
  });

  it("affiche DocumentInfoModal quand previewDoc est non nul", () => {
    render(<WorkspaceModals {...baseProps()} previewDoc={doc} />);

    expect(
      screen.getByRole("dialog", { name: "Informations du document" }),
    ).toBeInTheDocument();
    expect(screen.getByText("CCTP-lot-3.pdf")).toBeInTheDocument();
  });

  it("rend toujours BatchActionBar avec les props de sélection transmises", () => {
    render(<WorkspaceModals {...baseProps()} selectionCount={2} />);

    expect(screen.getByText("2 sélectionnés")).toBeInTheDocument();
  });
});

describe("WorkspaceModals — règles métier", () => {
  it("réinitialise currentFolderId quand le dossier supprimé est le dossier courant", async () => {
    const onConfirmDeleteFolder = vi.fn();
    const onCurrentFolderIdChange = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        deleteFolderTarget={folder}
        currentFolderId="folder-1"
        onConfirmDeleteFolder={onConfirmDeleteFolder}
        onCurrentFolderIdChange={onCurrentFolderIdChange}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onConfirmDeleteFolder).toHaveBeenCalledWith("folder-1");
    expect(onCurrentFolderIdChange).toHaveBeenCalledWith(null);
  });

  it("ne réinitialise pas currentFolderId quand le dossier supprimé n'est pas le dossier courant", async () => {
    const onCurrentFolderIdChange = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        deleteFolderTarget={folder}
        currentFolderId="another-folder"
        onCurrentFolderIdChange={onCurrentFolderIdChange}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Supprimer" }));

    expect(onCurrentFolderIdChange).not.toHaveBeenCalled();
  });

  it("propose Infos/Déplacer vers…/Supprimer pour une cible document", () => {
    render(
      <WorkspaceModals
        {...baseProps()}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "document", item: doc } }}
      />,
    );

    expect(screen.getByRole("menuitem", { name: "Infos" })).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Déplacer vers…" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Supprimer" })).toBeInTheDocument();
  });

  it("câble Infos au bon callback pour une cible document", async () => {
    const onPreviewDocChange = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        onPreviewDocChange={onPreviewDocChange}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "document", item: doc } }}
      />,
    );

    await userEvent.click(screen.getByRole("menuitem", { name: "Infos" }));
    expect(onPreviewDocChange).toHaveBeenCalledWith(doc);
  });

  it("câble Déplacer vers… au bon callback pour une cible document non déjà sélectionnée", async () => {
    const onToggleSelect = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        onToggleSelect={onToggleSelect}
        selectedIds={new Set()}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "document", item: doc } }}
      />,
    );

    await userEvent.click(screen.getByRole("menuitem", { name: "Déplacer vers…" }));
    expect(onToggleSelect).toHaveBeenCalledWith("doc-1");
  });

  it("Déplacer vers… ne re-sélectionne pas un document déjà sélectionné", async () => {
    const onToggleSelect = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        onToggleSelect={onToggleSelect}
        selectedIds={new Set(["doc-1"])}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "document", item: doc } }}
      />,
    );

    await userEvent.click(screen.getByRole("menuitem", { name: "Déplacer vers…" }));
    expect(onToggleSelect).not.toHaveBeenCalled();
  });

  it("propose Renommer/Lot-Phase/Supprimer pour une cible dossier", () => {
    render(
      <WorkspaceModals
        {...baseProps()}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "folder", item: folder } }}
      />,
    );

    expect(screen.getByRole("menuitem", { name: "Renommer" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Lot / Phase" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Supprimer" })).toBeInTheDocument();
  });

  it("câble Renommer au bon callback pour une cible dossier", async () => {
    const onEditingFolderIdChange = vi.fn();
    render(
      <WorkspaceModals
        {...baseProps()}
        onEditingFolderIdChange={onEditingFolderIdChange}
        contextMenu={{ position: { x: 0, y: 0 }, target: { type: "folder", item: folder } }}
      />,
    );

    await userEvent.click(screen.getByRole("menuitem", { name: "Renommer" }));
    expect(onEditingFolderIdChange).toHaveBeenCalledWith("folder-1");
  });
});

describe("WorkspaceModals — cas limites", () => {
  it("ne rend aucun item de menu contextuel quand contextMenu est nul", () => {
    render(<WorkspaceModals {...baseProps()} contextMenu={null} />);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
