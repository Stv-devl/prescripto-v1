import { ContextMenu } from "@/components/ui/ContextMenu";
import { BatchActionBar } from "@/features/projects";
import type { Document, Folder } from "@/features/projects";
import { DocumentModals } from "./DocumentModals";
import { FolderModals } from "./FolderModals";
import {
  getWorkspaceContextMenuItems,
  type ContextMenuTarget,
} from "./workspaceContextMenuItems";

interface WorkspaceModalsProps {
  deleteTarget: Document | null;
  onDeleteTargetChange: (doc: Document | null) => void;
  onConfirmDelete: (id: string) => void;
  isDeleting: boolean;
  showCreateFolder: boolean;
  onShowCreateFolderChange: (show: boolean) => void;
  onConfirmCreateFolder: (data: { name: string; lot: string; phase: string }) => void;
  isCreatingFolder: boolean;
  deleteFolderTarget: Folder | null;
  onDeleteFolderTargetChange: (folder: Folder | null) => void;
  onConfirmDeleteFolder: (id: string) => void;
  isDeletingFolder: boolean;
  currentFolderId: string | null;
  onCurrentFolderIdChange: (id: string | null) => void;
  editFolderTarget: Folder | null;
  onEditFolderTargetChange: (folder: Folder | null) => void;
  onConfirmEditFolder: (data: { folderId: string; lot?: string; phase?: string }) => void;
  isEditingFolder: boolean;
  previewDoc: Document | null;
  onPreviewDocChange: (doc: Document | null) => void;
  contextMenu: {
    position: { x: number; y: number };
    target: ContextMenuTarget;
  } | null;
  onContextMenuClose: () => void;
  onEditingFolderIdChange: (id: string | null) => void;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  selectionCount: number;
  folders: Folder[];
  onMoveSelected: (folderId: string | null) => void;
  onDeleteSelected: () => void;
  onClearSelection: () => void;
}

export function WorkspaceModals({
  deleteTarget,
  onDeleteTargetChange,
  onConfirmDelete,
  isDeleting,
  showCreateFolder,
  onShowCreateFolderChange,
  onConfirmCreateFolder,
  isCreatingFolder,
  deleteFolderTarget,
  onDeleteFolderTargetChange,
  onConfirmDeleteFolder,
  isDeletingFolder,
  currentFolderId,
  onCurrentFolderIdChange,
  editFolderTarget,
  onEditFolderTargetChange,
  onConfirmEditFolder,
  isEditingFolder,
  previewDoc,
  onPreviewDocChange,
  contextMenu,
  onContextMenuClose,
  onEditingFolderIdChange,
  selectedIds,
  onToggleSelect,
  selectionCount,
  folders,
  onMoveSelected,
  onDeleteSelected,
  onClearSelection,
}: WorkspaceModalsProps) {
  const contextMenuItems = getWorkspaceContextMenuItems(contextMenu, {
    onPreviewDocChange,
    onToggleSelect,
    selectedIds,
    onDeleteTargetChange,
    onEditingFolderIdChange,
    onEditFolderTargetChange,
    onDeleteFolderTargetChange,
  });

  return (
    <>
      <DocumentModals
        deleteTarget={deleteTarget}
        onDeleteTargetChange={onDeleteTargetChange}
        onConfirmDelete={onConfirmDelete}
        isDeleting={isDeleting}
        previewDoc={previewDoc}
        onPreviewDocChange={onPreviewDocChange}
      />

      <FolderModals
        showCreateFolder={showCreateFolder}
        onShowCreateFolderChange={onShowCreateFolderChange}
        onConfirmCreateFolder={onConfirmCreateFolder}
        isCreatingFolder={isCreatingFolder}
        deleteFolderTarget={deleteFolderTarget}
        onDeleteFolderTargetChange={onDeleteFolderTargetChange}
        onConfirmDeleteFolder={onConfirmDeleteFolder}
        isDeletingFolder={isDeletingFolder}
        currentFolderId={currentFolderId}
        onCurrentFolderIdChange={onCurrentFolderIdChange}
        editFolderTarget={editFolderTarget}
        onEditFolderTargetChange={onEditFolderTargetChange}
        onConfirmEditFolder={onConfirmEditFolder}
        isEditingFolder={isEditingFolder}
      />

      <ContextMenu
        isOpen={!!contextMenu}
        position={contextMenu?.position ?? { x: 0, y: 0 }}
        items={contextMenuItems}
        onClose={onContextMenuClose}
      />

      <BatchActionBar
        count={selectionCount}
        folders={folders}
        currentFolderId={currentFolderId}
        onMoveSelected={onMoveSelected}
        onDeleteSelected={onDeleteSelected}
        onClear={onClearSelection}
        isDeleting={isDeleting}
      />
    </>
  );
}

export { type ContextMenuTarget };
