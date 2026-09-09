import { useEffect, useMemo, useState } from "react";
import type { Folder, useFolders } from "@/features/projects";

interface FolderSelectionResult {
  currentFolderId: string | null;
  setCurrentFolderId: (id: string | null) => void;
  currentFolder: Folder | null;
  folderOptions: Folder[];
}

/** The current-folder state, its lookup, and clearing the selection when it changes. */
export function useFolderSelection(
  folders: ReturnType<typeof useFolders>,
  clear: () => void,
): FolderSelectionResult {
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);

  useEffect(() => {
    clear();
  }, [currentFolderId, clear]);

  const currentFolder = useMemo(() => {
    if (!currentFolderId || !folders.data) return null;
    return folders.data.folders.find((f) => f.id === currentFolderId) ?? null;
  }, [currentFolderId, folders.data]);

  const folderOptions = folders.data?.folders ?? [];

  return { currentFolderId, setCurrentFolderId, currentFolder, folderOptions };
}
