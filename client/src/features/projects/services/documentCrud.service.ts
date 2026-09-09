import { apiGet, apiPatch, apiDelete } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { Document, DocumentList } from "../types/types";

/**
 * Lists documents for a project.
 */
export function listDocuments(
  projectId: string,
): Promise<Result<DocumentList>> {
  return attempt(() =>
    apiGet<DocumentList>(`/projects/${projectId}/documents`),
  );
}

/**
 * Deletes a document by ID.
 */
export function deleteDocument(documentId: string): Promise<Result<void>> {
  return attempt(() => apiDelete(`/documents/${documentId}`));
}

/**
 * Moves a document to a folder, or to the root when `folderId` is null.
 */
export function moveDocument(
  documentId: string,
  folderId: string | null,
): Promise<Result<Document>> {
  return attempt(() =>
    apiPatch<Document>(`/documents/${documentId}/move`, {
      folder_id: folderId,
    }),
  );
}
