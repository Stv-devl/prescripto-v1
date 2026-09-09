import { AnimatePresence } from "framer-motion";
import { useDocumentListSelection } from "../hooks/useDocumentListSelection";
import { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import type { SortDirection, SortField } from "../utils/documentDisplay";
import { DocumentListFolderRow } from "./DocumentListFolderRow";
import { DocumentListHeaderRow } from "./DocumentListHeaderRow";
import { DocumentListRootDropRow } from "./DocumentListRootDropRow";
import { DocumentListRow } from "./DocumentListRow";

/** Re-exported for callers that still import these from this module. */
export type { SortField, SortDirection } from "../utils/documentDisplay";
export { STATUS_STYLES, STATUS_LABELS, getFileIcon, ProcessingProgress } from "../utils/documentDisplay";

interface DocumentListProps {
  documents: Document[];
  onDelete: (doc: Document) => void;
  isDeleting: boolean;
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
  folders?: Folder[];
  onMoveDocument?: (documentId: string, folderId: string | null) => void;
  onOpenFolder?: (folderId: string) => void;
  onDeleteFolder?: (folder: Folder) => void;
  onRenameFolder?: (folderId: string, name: string) => void;
  isRenamingFolder?: boolean;
  currentFolderId?: string | null;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onToggleSelectAll?: (allIds: string[]) => void;
  onDocumentClick?: (doc: Document) => void;
  onContextMenu?: (
    e: React.MouseEvent,
    target:
      | { type: "document"; item: Document }
      | { type: "folder"; item: Folder },
  ) => void;
  editingFolderIdExternal?: string | null;
  onEditingFolderIdChange?: (id: string | null) => void;
  onFileDropOnFolder?: (files: File[], folderId: string) => void;
  onFileDrop?: (e: React.DragEvent) => void;
}

export function DocumentList({
  documents,
  onDelete,
  isDeleting,
  sortField,
  sortDirection,
  onSort,
  folders = [],
  onMoveDocument,
  onOpenFolder,
  onDeleteFolder,
  onRenameFolder,
  isRenamingFolder = false,
  currentFolderId = null,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onDocumentClick,
  onContextMenu,
  editingFolderIdExternal,
  onEditingFolderIdChange,
  onFileDropOnFolder,
  onFileDrop,
}: DocumentListProps) {
  const {
    hasSelection,
    allSelected,
    partiallySelected,
    editingFolderId,
    setEditingFolderId,
  } = useDocumentListSelection(
    documents,
    selectedIds,
    onToggleSelect,
    editingFolderIdExternal,
    onEditingFolderIdChange,
  );

  const dd = useFolderDragDrop({ onMoveDocument, onFileDropOnFolder, onFileDrop });
  const docIds = documents.map((d) => d.id);

  return (
    <table
      className="w-full text-sm [&_tr>*:first-child]:pl-4 [&_tr>*:last-child]:pr-4"
      onDragOver={dd.handleContainerDragOver}
      onDrop={dd.handleContainerDrop}
    >
      <thead>
        <DocumentListHeaderRow
          hasSelection={hasSelection}
          allSelected={allSelected}
          partiallySelected={partiallySelected}
          docIds={docIds}
          onToggleSelectAll={onToggleSelectAll}
          sortField={sortField}
          sortDirection={sortDirection}
          onSort={onSort}
        />
      </thead>
      <AnimatePresence mode="popLayout">
        <tbody>
          {currentFolderId && onMoveDocument && (
            <DocumentListRootDropRow
              hasSelection={hasSelection}
              dragOverRoot={dd.dragOverRoot}
              onDragOver={dd.handleRootDragOver}
              onDrop={dd.handleRootDrop}
              onDragLeave={() => dd.setDragOverRoot(false)}
            />
          )}
          {folders.map((folder) => (
            <DocumentListFolderRow
              key={`folder-${folder.id}`}
              folder={folder}
              hasSelection={hasSelection}
              editingFolderId={editingFolderId}
              onStartRename={setEditingFolderId}
              onCancelRename={() => setEditingFolderId(null)}
              onRenameFolder={onRenameFolder}
              isRenamingFolder={isRenamingFolder}
              onDeleteFolder={onDeleteFolder}
              onOpenFolder={onOpenFolder}
              onContextMenu={onContextMenu}
              dd={dd}
            />
          ))}
          {documents.map((doc) => (
            <DocumentListRow
              key={doc.id}
              doc={doc}
              isSelected={selectedIds?.has(doc.id) ?? false}
              hasSelection={hasSelection}
              onToggleSelect={onToggleSelect}
              onDocumentClick={onDocumentClick}
              onContextMenu={onContextMenu}
              onDelete={onDelete}
              isDeleting={isDeleting}
              draggable={!!onMoveDocument}
              dd={dd}
            />
          ))}
        </tbody>
      </AnimatePresence>
    </table>
  );
}
