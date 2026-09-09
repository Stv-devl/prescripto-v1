import { useState } from "react";
import type { Document } from "../types/types";

interface DocumentListSelection {
  hasSelection: boolean;
  allSelected: boolean;
  partiallySelected: boolean;
  editingFolderId: string | null;
  setEditingFolderId: (id: string | null) => void;
}

/**
 * `DocumentList`'s selection derivation and folder-rename edit state
 * (controlled via `editingFolderIdExternal`, or internal otherwise).
 */
export function useDocumentListSelection(
  documents: Document[],
  selectedIds: Set<string> | undefined,
  onToggleSelect: ((id: string) => void) | undefined,
  editingFolderIdExternal: string | null | undefined,
  onEditingFolderIdChange: ((id: string | null) => void) | undefined,
): DocumentListSelection {
  const [editingFolderIdInternal, setEditingFolderIdInternal] = useState<
    string | null
  >(null);
  const editingFolderId = editingFolderIdExternal ?? editingFolderIdInternal;
  const setEditingFolderId = (id: string | null): void => {
    setEditingFolderIdInternal(id);
    onEditingFolderIdChange?.(id);
  };

  const hasSelection = !!selectedIds && !!onToggleSelect;
  const docIds = documents.map((d) => d.id);
  const allSelected =
    hasSelection &&
    docIds.length > 0 &&
    docIds.every((id) => selectedIds.has(id));
  const partiallySelected =
    hasSelection && docIds.some((id) => selectedIds.has(id)) && !allSelected;

  return {
    hasSelection,
    allSelected,
    partiallySelected,
    editingFolderId,
    setEditingFolderId,
  };
}
