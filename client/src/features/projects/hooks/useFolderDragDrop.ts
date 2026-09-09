import { useState, useRef } from "react";
import type { Document } from "../types/types";
import { createDragGhost } from "../utils/documentDisplay";
import {
  isExternalFileDrop,
  readDirectoryEntries,
  isSupportedFile,
} from "../utils/dragUtils";

interface UseFolderDragDropOptions {
  onMoveDocument?: (documentId: string, folderId: string | null) => void;
  onFileDropOnFolder?: (files: File[], folderId: string) => void;
  onFileDrop?: (e: React.DragEvent) => void;
}

/**
 * Shared drag-and-drop logic for DocumentList and DocumentGrid.
 * Handles document drag, folder drop targets, root drop, and external file drops.
 */
export function useFolderDragDrop({
  onMoveDocument,
  onFileDropOnFolder,
  onFileDrop,
}: UseFolderDragDropOptions) {
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null);
  const [dragOverRoot, setDragOverRoot] = useState(false);
  const [externalDragOverFolderId, setExternalDragOverFolderId] = useState<
    string | null
  >(null);
  const [draggingDocId, setDraggingDocId] = useState<string | null>(null);
  const ghostRef = useRef<HTMLElement | null>(null);

  function handleDragStart(e: React.DragEvent, doc: Document): void {
    e.dataTransfer.setData("text/plain", doc.id);
    e.dataTransfer.effectAllowed = "move";
    setDraggingDocId(doc.id);

    const ghost = createDragGhost(doc.filename);
    ghostRef.current = ghost;
    e.dataTransfer.setDragImage(ghost, 0, 0);
    requestAnimationFrame(() => {
      if (ghostRef.current) {
        document.body.removeChild(ghostRef.current);
        ghostRef.current = null;
      }
    });
  }

  function handleDragEnd(): void {
    setDraggingDocId(null);
    setDragOverFolderId(null);
    setDragOverRoot(false);
  }

  function handleFolderDragOver(e: React.DragEvent, folderId: string): void {
    e.preventDefault();
    if (isExternalFileDrop(e)) {
      e.dataTransfer.dropEffect = "copy";
      setExternalDragOverFolderId(folderId);
    } else {
      e.dataTransfer.dropEffect = "move";
      setDragOverFolderId(folderId);
    }
  }

  async function handleFolderDrop(
    e: React.DragEvent,
    folderId: string,
  ): Promise<void> {
    e.preventDefault();
    e.stopPropagation();
    if (isExternalFileDrop(e)) {
      setExternalDragOverFolderId(null);
      const allFiles: File[] = [];
      const items = e.dataTransfer.items;

      if (items && items.length > 0) {
        for (let i = 0; i < items.length; i++) {
          const entry = items[i].webkitGetAsEntry?.();
          if (entry?.isDirectory) {
            const dirFiles = await readDirectoryEntries(
              entry as FileSystemDirectoryEntry,
            );
            allFiles.push(...dirFiles.filter(isSupportedFile));
          } else if (entry?.isFile) {
            const file = items[i].getAsFile();
            if (file) allFiles.push(file);
          }
        }
      } else {
        allFiles.push(...Array.from(e.dataTransfer.files));
      }

      if (allFiles.length > 0) onFileDropOnFolder?.(allFiles, folderId);
    } else {
      const docId = e.dataTransfer.getData("text/plain");
      if (docId && onMoveDocument) {
        onMoveDocument(docId, folderId);
      }
      setDragOverFolderId(null);
      setDraggingDocId(null);
    }
  }

  function handleFolderDragLeave(): void {
    setDragOverFolderId(null);
    setExternalDragOverFolderId(null);
  }

  function handleRootDragOver(e: React.DragEvent): void {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverRoot(true);
  }

  function handleRootDrop(e: React.DragEvent): void {
    e.preventDefault();
    const docId = e.dataTransfer.getData("text/plain");
    if (docId && onMoveDocument) {
      onMoveDocument(docId, null);
    }
    setDragOverRoot(false);
    setDraggingDocId(null);
  }

  function handleContainerDragOver(e: React.DragEvent): void {
    if (isExternalFileDrop(e)) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    }
  }

  function handleContainerDrop(e: React.DragEvent): void {
    if (isExternalFileDrop(e)) {
      e.preventDefault();
      e.stopPropagation();
      onFileDrop?.(e);
    }
  }

  return {
    dragOverFolderId,
    dragOverRoot,
    externalDragOverFolderId,
    draggingDocId,
    handleDragStart,
    handleDragEnd,
    handleFolderDragOver,
    handleFolderDrop,
    handleFolderDragLeave,
    handleRootDragOver,
    handleRootDrop,
    handleContainerDragOver,
    handleContainerDrop,
    setDragOverRoot,
  } as const;
}
