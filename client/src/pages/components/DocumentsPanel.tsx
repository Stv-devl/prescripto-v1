import type { Document, Folder, SortDirection, SortField } from "@/features/projects";
import { DocumentsCollection } from "./DocumentsCollection";
import { DocumentsToolbar } from "./DocumentsToolbar";
import { FolderBreadcrumb } from "./FolderBreadcrumb";
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

interface DocumentsPanelProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  search: string;
  onSearchChange: (value: string) => void;
  summary: string | null;
  currentFolderId: string | null;
  currentFolder: Folder | null;
  onOpenFolder: (folderId: string | null) => void;
  onShowCreateFolder: () => void;
  sortedDocuments: Document[];
  folderOptions: Folder[];
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
  onToggleSelectAll: (ids: string[]) => void;
  sharedDocProps: SharedDocProps;
}

/** The toolbar, breadcrumb and document collection shown once documents/folders exist. */
export function DocumentsPanel({
  viewMode,
  onViewModeChange,
  search,
  onSearchChange,
  summary,
  currentFolderId,
  currentFolder,
  onOpenFolder,
  onShowCreateFolder,
  sortedDocuments,
  folderOptions,
  sortField,
  sortDirection,
  onSort,
  onToggleSelectAll,
  sharedDocProps,
}: DocumentsPanelProps) {
  return (
    <>
      <DocumentsToolbar
        viewMode={viewMode}
        onViewModeChange={onViewModeChange}
        search={search}
        onSearchChange={onSearchChange}
        canCreateFolder={!currentFolderId}
        onShowCreateFolder={onShowCreateFolder}
        summary={summary}
      />

      {currentFolderId && currentFolder && (
        <FolderBreadcrumb
          folder={currentFolder}
          documentCount={sortedDocuments.length}
          onBack={() => onOpenFolder(null)}
        />
      )}

      <DocumentsCollection
        viewMode={viewMode}
        sortedDocuments={sortedDocuments}
        currentFolderId={currentFolderId}
        folderOptions={folderOptions}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={onSort}
        onToggleSelectAll={onToggleSelectAll}
        sharedDocProps={sharedDocProps}
      />
    </>
  );
}
