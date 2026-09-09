import {
  CreateFolderModal,
  DeleteFolderModal,
  EditFolderModal,
} from "@/features/projects";
import type { Folder } from "@/features/projects";

interface FolderModalsProps {
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
}

export function FolderModals({
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
}: FolderModalsProps) {
  return (
    <>
      {showCreateFolder && (
        <CreateFolderModal
          isPending={isCreatingFolder}
          onConfirm={(data) => {
            onConfirmCreateFolder(data);
            onShowCreateFolderChange(false);
          }}
          onClose={() => onShowCreateFolderChange(false)}
        />
      )}

      {deleteFolderTarget && (
        <DeleteFolderModal
          folderName={deleteFolderTarget.name}
          isPending={isDeletingFolder}
          onConfirm={() => {
            onConfirmDeleteFolder(deleteFolderTarget.id);
            if (currentFolderId === deleteFolderTarget.id) {
              onCurrentFolderIdChange(null);
            }
          }}
          onClose={() => onDeleteFolderTargetChange(null)}
        />
      )}

      {editFolderTarget && (
        <EditFolderModal
          folder={editFolderTarget}
          isPending={isEditingFolder}
          onConfirm={(data) =>
            onConfirmEditFolder({ folderId: editFolderTarget.id, ...data })
          }
          onClose={() => onEditFolderTargetChange(null)}
        />
      )}
    </>
  );
}
