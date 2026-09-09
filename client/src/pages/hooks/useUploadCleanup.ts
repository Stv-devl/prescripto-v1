import { useEffect, useMemo } from "react";
import type { Document } from "@/features/projects";

interface UploadEntry {
  resolvedDocId: string | null;
}

/** Removes an upload store entry once its real document appears in the cache. */
export function useUploadCleanup(
  uploads: Record<string, UploadEntry>,
  documents: Document[] | undefined,
  removeUpload: (id: string) => void,
): void {
  const realDocIds = useMemo(
    () => new Set(documents?.map((d) => d.id) ?? []),
    [documents],
  );

  useEffect(() => {
    for (const [uploadId, entry] of Object.entries(uploads)) {
      if (entry.resolvedDocId && realDocIds.has(entry.resolvedDocId)) {
        removeUpload(uploadId);
      }
    }
  }, [uploads, realDocIds, removeUpload]);
}
