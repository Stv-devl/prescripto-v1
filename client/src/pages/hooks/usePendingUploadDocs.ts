import { useMemo } from "react";
import type { Document } from "@/features/projects";

interface UploadEntry {
  fileName: string;
  folderId: string | null;
  status: "uploading" | "processing" | "ready" | "error";
  resolvedDocId: string | null;
}

/** Optimistic document rows for uploads still in flight in the current folder. */
export function usePendingUploadDocs(
  uploads: Record<string, UploadEntry>,
  currentFolderId: string | null,
  projectId: string,
): Document[] {
  return useMemo((): Document[] => {
    return Object.entries(uploads)
      .filter(
        ([, entry]) =>
          entry.folderId === currentFolderId &&
          (entry.status === "uploading" || entry.status === "processing"),
      )
      .map(([id, entry]) => ({
        id: entry.resolvedDocId ?? id,
        project_id: projectId,
        folder_id: entry.folderId,
        filename: entry.fileName,
        type: "",
        lot: "",
        phase: "",
        size: 0,
        status: entry.status as "uploading" | "processing",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }));
  }, [uploads, currentFolderId, projectId]);
}
