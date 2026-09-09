import { EmptyState } from "@/components/feedback/EmptyState";
import { DocumentGrid, DocumentList } from "@/features/projects";
import type {
  Document,
  Folder,
  SortDirection,
  SortField,
} from "@/features/projects";
import type { ContextMenuTarget } from "./workspaceContextMenuItems";

type ViewMode = "list" | "grid";

interface SharedDocProps {
  documents: Document[];
  onDelete: (doc: Document) => void;
  isDeleting: boolean;
  folders: Folder[];
  onMoveDocument: (documentId: string, folderId: string | null) => void;
  onOpenFolder: (folderId: string | null) => void;
  onDeleteFolder: (folder: Folder) => void;
  onRenameFolder: (folderId: string, name: string) => void;
  isRenamingFolder: boolean;
  currentFolderId: string | null;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onContextMenu: (e: React.MouseEvent, target: ContextMenuTarget) => void;
  editingFolderIdExternal: string | null;
  onEditingFolderIdChange: (id: string | null) => void;
  onFileDropOnFolder: (files: File[], folderId: string) => void;
  onFileDrop: (e: React.DragEvent) => void;
}

interface DocumentsCollectionProps {
  viewMode: ViewMode;
  sortedDocuments: Document[];
  currentFolderId: string | null;
  folderOptions: Folder[];
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
  onToggleSelectAll: (ids: string[]) => void;
  sharedDocProps: SharedDocProps;
}

export function DocumentsCollection({
  viewMode,
  sortedDocuments,
  currentFolderId,
  folderOptions,
  sortField,
  sortDirection,
  onSort,
  onToggleSelectAll,
  sharedDocProps,
}: DocumentsCollectionProps) {
  if (
    sortedDocuments.length === 0 &&
    (currentFolderId !== null || folderOptions.length === 0)
  ) {
    return (
      <EmptyState
        message={
          currentFolderId
            ? "Ce dossier est vide."
            : "Aucun document ne correspond à votre recherche."
        }
      />
    );
  }

  if (viewMode === "list") {
    return (
      <DocumentList
        {...sharedDocProps}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={onSort}
        onToggleSelectAll={onToggleSelectAll}
      />
    );
  }

  return <DocumentGrid {...sharedDocProps} />;
}
