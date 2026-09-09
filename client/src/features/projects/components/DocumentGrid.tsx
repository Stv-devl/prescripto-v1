import { AnimatePresence } from "framer-motion";
import { useState } from "react";
import { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import { DocumentGridDocumentCard } from "./DocumentGridDocumentCard";
import { DocumentGridFolderCard } from "./DocumentGridFolderCard";
import { DocumentGridRootDropCard } from "./DocumentGridRootDropCard";

interface DocumentGridProps {
  documents: Document[];
  onDelete: (doc: Document) => void;
  isDeleting: boolean;
  folders?: Folder[];
  onMoveDocument?: (documentId: string, folderId: string | null) => void;
  onOpenFolder?: (folderId: string) => void;
  onDeleteFolder?: (folder: Folder) => void;
  onRenameFolder?: (folderId: string, name: string) => void;
  isRenamingFolder?: boolean;
  currentFolderId?: string | null;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
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

export function DocumentGrid({
  documents,
  onDelete,
  isDeleting,
  folders = [],
  onMoveDocument,
  onOpenFolder,
  onDeleteFolder,
  onRenameFolder,
  isRenamingFolder = false,
  currentFolderId = null,
  selectedIds,
  onToggleSelect,
  onDocumentClick,
  onContextMenu,
  editingFolderIdExternal,
  onEditingFolderIdChange,
  onFileDropOnFolder,
  onFileDrop,
}: DocumentGridProps) {
  const [editingFolderIdInternal, setEditingFolderIdInternal] = useState<
    string | null
  >(null);
  const editingFolderId = editingFolderIdExternal ?? editingFolderIdInternal;
  const setEditingFolderId = (id: string | null): void => {
    setEditingFolderIdInternal(id);
    onEditingFolderIdChange?.(id);
  };

  const dd = useFolderDragDrop({ onMoveDocument, onFileDropOnFolder, onFileDrop });

  const hasSelection = !!selectedIds && !!onToggleSelect;
  const hasFolders = folders.length > 0 || (currentFolderId && onMoveDocument);

  return (
    <div
      className="flex flex-col gap-5"
      onDragOver={dd.handleContainerDragOver}
      onDrop={dd.handleContainerDrop}
    >
      {/* Folders section — compact separate grid */}
      {hasFolders && (
        <section>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
            <AnimatePresence mode="popLayout">
              {currentFolderId && onMoveDocument && (
                <DocumentGridRootDropCard
                  dragOverRoot={dd.dragOverRoot}
                  onDragOver={dd.handleRootDragOver}
                  onDrop={dd.handleRootDrop}
                  onDragLeave={() => dd.setDragOverRoot(false)}
                />
              )}

              {folders.map((folder) => (
                <DocumentGridFolderCard
                  key={`folder-${folder.id}`}
                  folder={folder}
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
            </AnimatePresence>
          </div>
        </section>
      )}

      {/* Documents grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <AnimatePresence mode="popLayout">
          {documents.map((doc) => (
            <DocumentGridDocumentCard
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
        </AnimatePresence>
      </div>
    </div>
  );
}
