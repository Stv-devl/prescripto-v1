import { useCallback, useMemo, useState } from "react";
import type { Document, SortDirection, SortField } from "@/features/projects";

interface SortedDocumentsResult {
  sortField: SortField;
  sortDirection: SortDirection;
  sortedDocuments: Document[];
  handleSort: (field: SortField) => void;
}

/** Filters by folder and search text, then sorts, then merges in pending uploads. */
export function useSortedDocuments(
  documents: Document[] | undefined,
  currentFolderId: string | null,
  search: string,
  pendingUploadDocs: Document[],
): SortedDocumentsResult {
  const [sortField, setSortField] = useState<SortField>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const sortedDocuments = useMemo(() => {
    if (!documents) return pendingUploadDocs;

    const folderFiltered =
      currentFolderId === null
        ? documents.filter((d) => d.folder_id === null)
        : documents.filter((d) => d.folder_id === currentFolderId);

    const query = search.toLowerCase().trim();
    const filtered = query
      ? folderFiltered.filter(
          (d) =>
            d.filename.toLowerCase().includes(query) ||
            (d.type ?? "").toLowerCase().includes(query) ||
            (d.lot ?? "").toLowerCase().includes(query) ||
            (d.phase ?? "").toLowerCase().includes(query),
        )
      : folderFiltered;

    const sorted = [...filtered].sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;

      switch (sortField) {
        case "size":
          return (a.size - b.size) * dir;
        case "created_at":
          return (
            (new Date(a.created_at).getTime() -
              new Date(b.created_at).getTime()) *
            dir
          );
        case "filename":
        case "type":
        case "lot":
        case "phase":
        case "status":
          return (
            (a[sortField] ?? "").localeCompare(b[sortField] ?? "", "fr") * dir
          );
        default:
          return 0;
      }
    });

    const realIds = new Set(sorted.map((d) => d.id));
    const pending = pendingUploadDocs.filter((d) => !realIds.has(d.id));
    return [...sorted, ...pending];
  }, [documents, sortField, sortDirection, search, currentFolderId, pendingUploadDocs]);

  const handleSort = useCallback(
    (field: SortField) => {
      if (field === sortField) {
        setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortField(field);
        setSortDirection("asc");
      }
    },
    [sortField],
  );

  return { sortField, sortDirection, sortedDocuments, handleSort };
}
