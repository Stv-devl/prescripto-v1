import { useState, useCallback, useEffect, useRef } from "react";
import {
  isExternalFileDrop,
  readDirectoryEntries,
  isSupportedFile,
} from "@/features/projects";

interface UseWorkspaceDragDropOptions {
  onFileDropOnBody: (files: File[]) => void;
  onFolderDrop: (folderName: string, files: File[]) => void;
}

/**
 * Encapsulates external file drag-and-drop handling
 * for the documents section of ProjectWorkspacePage.
 *
 * A global drop listener resets the overlay as a safety net: a `dragleave`
 * missed on a fast drop would otherwise leave it stuck on screen.
 */
export function useWorkspaceDragDrop({
  onFileDropOnBody,
  onFolderDrop,
}: UseWorkspaceDragDropOptions) {
  const [externalDragOver, setExternalDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  useEffect(() => {
    const handleGlobalDrop = (): void => {
      dragCounterRef.current = 0;
      setExternalDragOver(false);
    };
    document.addEventListener("drop", handleGlobalDrop, true);
    return () => document.removeEventListener("drop", handleGlobalDrop, true);
  }, []);

  const resetDragState = useCallback(() => {
    dragCounterRef.current = 0;
    setExternalDragOver(false);
  }, []);

  const handleSectionDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (isExternalFileDrop(e)) {
      dragCounterRef.current++;
      setExternalDragOver(true);
    }
  }, []);

  const handleSectionDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (isExternalFileDrop(e)) {
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const handleSectionDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (isExternalFileDrop(e)) {
      dragCounterRef.current--;
      if (dragCounterRef.current <= 0) {
        dragCounterRef.current = 0;
        setExternalDragOver(false);
      }
    }
  }, []);

  const handleSectionDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      dragCounterRef.current = 0;
      setExternalDragOver(false);
      const nativeEvent = e.nativeEvent as Event & { _handled?: boolean };
      if (nativeEvent._handled) return;
      nativeEvent._handled = true;
      if (!isExternalFileDrop(e)) return;

      const items = e.dataTransfer.items;
      if (!items || items.length === 0) {
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) onFileDropOnBody(files);
        return;
      }

      const folderEntries: {
        name: string;
        entry: FileSystemDirectoryEntry;
      }[] = [];
      const looseFiles: File[] = [];

      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.();
        if (entry?.isDirectory) {
          folderEntries.push({
            name: entry.name,
            entry: entry as FileSystemDirectoryEntry,
          });
        } else if (entry?.isFile) {
          const file = items[i].getAsFile();
          if (file) looseFiles.push(file);
        }
      }

      for (const { name, entry } of folderEntries) {
        const allFiles = await readDirectoryEntries(entry);
        const supported = allFiles.filter(isSupportedFile);
        if (supported.length > 0) {
          onFolderDrop(name, supported);
        }
      }

      if (looseFiles.length > 0) onFileDropOnBody(looseFiles);
    },
    [onFileDropOnBody, onFolderDrop],
  );

  return {
    externalDragOver,
    resetDragState,
    handleSectionDragEnter,
    handleSectionDragOver,
    handleSectionDragLeave,
    handleSectionDrop,
  } as const;
}
