import {
  uploadFile,
  uploadFileWithProgress,
  uploadFileWithProgressAndFields,
} from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { Document } from "../types/types";

/**
 * Uploads a file to a project (no progress tracking).
 */
export function uploadDocument(
  projectId: string,
  file: File,
): Promise<Result<Document>> {
  return attempt(() =>
    uploadFile<Document>(`/projects/${projectId}/documents`, file),
  );
}

/**
 * Uploads a file to a project with progress tracking.
 */
export function uploadDocumentWithProgress(
  projectId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<Result<Document>> {
  return attempt(() =>
    uploadFileWithProgress<Document>(
      `/projects/${projectId}/documents`,
      file,
      onProgress,
    ),
  );
}

/**
 * Uploads a file to a specific folder in a project with progress tracking.
 */
export function uploadDocumentToFolder(
  projectId: string,
  file: File,
  folderId: string,
  onProgress: (percent: number) => void,
): Promise<Result<Document>> {
  return attempt(() =>
    uploadFileWithProgressAndFields<Document>(
      `/projects/${projectId}/documents`,
      file,
      { folder_id: folderId },
      onProgress,
    ),
  );
}
