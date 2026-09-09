import { useState } from "react";
import { DocumentUpload } from "@/features/projects";
import type { Document, Folder, SortField, SortDirection } from "@/features/projects";
import { DocumentsPanel } from "./DocumentsPanel";
import { DocumentsSectionState } from "./DocumentsSectionState";
import type { ContextMenuTarget } from "./workspaceContextMenuItems";

type ViewMode = "list" | "grid";

interface WorkspaceDocumentsTabProps {
  projectId: string;
  sortedDocuments: Document[];
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
  search: string;
  onSearchChange: (value: string) => void;
  summary: string | null;
  currentFolderId: string | null;
  onOpenFolder: (folderId: string | null) => void;
  currentFolder: Folder | null;
  folderOptions: Folder[];
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleSelectAll: (ids: string[]) => void;
  onDeleteDocument: (doc: Document) => void;
  onMoveDocument: (documentId: string, folderId: string | null) => void;
  onDeleteFolder: (folder: Folder) => void;
  onRenameFolder: (folderId: string, name: string) => void;
  isRenamingFolder: boolean;
  onShowCreateFolder: () => void;
  externalDragOver: boolean;
  onSectionDragEnter: (e: React.DragEvent) => void;
  onSectionDragOver: (e: React.DragEvent) => void;
  onSectionDragLeave: (e: React.DragEvent) => void;
  onSectionDrop: (e: React.DragEvent) => void;
  onFileDropOnFolder: (files: File[], folderId: string) => void;
  onContextMenu: (e: React.MouseEvent, target: ContextMenuTarget) => void;
  editingFolderIdExternal: string | null;
  onEditingFolderIdChange: (id: string | null) => void;
  isDocsPending: boolean;
  docsError: Error | null;
  hasDocuments: boolean;
  hasFolders: boolean;
}

export function WorkspaceDocumentsTab({
  projectId,
  sortedDocuments,
  sortField,
  sortDirection,
  onSort,
  search,
  onSearchChange,
  summary,
  currentFolderId,
  onOpenFolder,
  currentFolder,
  folderOptions,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onDeleteDocument,
  onMoveDocument,
  onDeleteFolder,
  onRenameFolder,
  isRenamingFolder,
  onShowCreateFolder,
  externalDragOver,
  onSectionDragEnter,
  onSectionDragOver,
  onSectionDragLeave,
  onSectionDrop,
  onFileDropOnFolder,
  onContextMenu,
  editingFolderIdExternal,
  onEditingFolderIdChange,
  isDocsPending,
  docsError,
  hasDocuments,
  hasFolders,
}: WorkspaceDocumentsTabProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("list");

  const sharedDocProps = {
    documents: sortedDocuments,
    onDelete: onDeleteDocument,
    isDeleting: false,
    folders: currentFolderId === null ? folderOptions : [],
    onMoveDocument,
    onOpenFolder,
    onDeleteFolder,
    onRenameFolder,
    isRenamingFolder,
    currentFolderId,
    selectedIds,
    onToggleSelect,
    onContextMenu,
    editingFolderIdExternal,
    onEditingFolderIdChange,
    onFileDropOnFolder,
    onFileDrop: onSectionDrop,
  } as const;

  return (
    <section
      className={`h-full overflow-y-auto p-6 transition-all ${externalDragOver ? "ring-2 ring-inset ring-dashed ring-[#FFC300]/60 bg-[#FFC300]/5" : ""}`}
      aria-label="Documents du projet"
      onDragEnter={onSectionDragEnter}
      onDragOver={onSectionDragOver}
      onDragLeave={onSectionDragLeave}
      onDrop={onSectionDrop}
    >
      <DocumentUpload projectId={projectId} />

      <div className="mt-6">
        <DocumentsSectionState
          isDocsPending={isDocsPending}
          docsError={docsError}
          hasDocuments={hasDocuments}
          hasFolders={hasFolders}
        />

        {(hasDocuments || hasFolders) && (
          <DocumentsPanel
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            search={search}
            onSearchChange={onSearchChange}
            summary={summary}
            currentFolderId={currentFolderId}
            currentFolder={currentFolder}
            onOpenFolder={onOpenFolder}
            onShowCreateFolder={onShowCreateFolder}
            sortedDocuments={sortedDocuments}
            folderOptions={folderOptions}
            sortField={sortField}
            sortDirection={sortDirection}
            onSort={onSort}
            onToggleSelectAll={onToggleSelectAll}
            sharedDocProps={sharedDocProps}
          />
        )}
      </div>
    </section>
  );
}
