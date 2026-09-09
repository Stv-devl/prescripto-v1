import { useQueryClient } from "@tanstack/react-query";
import { useState, useCallback, useRef, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { unwrap } from "@/lib/result";
import { beginSessionScope } from "@/lib/store/sessionReset";
import { createProject } from "../services/projects.service";
import { usePendingFolderUploadStore } from "../stores/pendingFolderUploadStore";
import { readDirectoryEntries, isSupportedFile } from "../utils/dragUtils";

interface UseProjectsPageDropReturn {
  isDragOver: boolean;
  isCreating: boolean;
  onDragEnter: (e: DragEvent) => void;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => Promise<void>;
}

/**
 * Handles drag & drop of OS folders on the projects list page.
 * Creates a project named after the folder, stores files for upload,
 * then navigates to the new project workspace.
 */
export function useProjectsPageDrop(): UseProjectsPageDropReturn {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setPending = usePendingFolderUploadStore((s) => s.setPending);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const dragCounterRef = useRef(0);

  const onDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    if (!e.dataTransfer.types.includes("Files")) return;
    dragCounterRef.current += 1;
    if (dragCounterRef.current === 1) setIsDragOver(true);
  }, []);

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.types.includes("Files")) {
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const onDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const onDrop = useCallback(
    async (e: DragEvent) => {
      const inSession = beginSessionScope();
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);

      const items = e.dataTransfer.items;
      if (!items || items.length === 0) return;

      let folderEntry: FileSystemDirectoryEntry | null = null;
      let folderName = "";

      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.();
        if (entry?.isDirectory) {
          folderEntry = entry as FileSystemDirectoryEntry;
          folderName = entry.name;
          break;
        }
      }

      if (!folderEntry) return;

      const allFiles = await readDirectoryEntries(folderEntry);
      const supported = allFiles.filter(isSupportedFile);
      if (supported.length === 0) return;

      const stillSameSession = inSession(() => undefined);
      if (!stillSameSession) return;

      setIsCreating(true);
      try {
        const [created] = await Promise.all([
          createProject({ name: folderName, phase: "" }),
          new Promise((r) => setTimeout(r, 800)),
        ]);
        const project = unwrap(created);
        await queryClient.invalidateQueries({ queryKey: ["projects"] });
        const opened = inSession(() => {
          setPending({ folderName, files: supported });
          navigate(`/projects/${project.id}`);
        });
        if (!opened) setIsCreating(false);
      } catch (err) {
        console.error("Failed to create project from dropped folder", err);
        setIsCreating(false);
      }
    },
    [navigate, setPending, queryClient],
  );

  return {
    isDragOver,
    isCreating,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  };
}
