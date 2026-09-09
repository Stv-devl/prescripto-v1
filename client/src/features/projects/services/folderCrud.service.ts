import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { Folder, FolderList, CreateFolderInput } from "../types/types";

/**
 * Lists folders for a project.
 */
export function listFolders(projectId: string): Promise<Result<FolderList>> {
  return attempt(() => apiGet<FolderList>(`/projects/${projectId}/folders`));
}

/**
 * Creates a new folder in a project.
 */
export function createFolder(
  projectId: string,
  data: CreateFolderInput,
): Promise<Result<Folder>> {
  return attempt(() =>
    apiPost<Folder>(`/projects/${projectId}/folders`, data),
  );
}

/**
 * Updates a folder (name, lot, phase).
 */
export function updateFolder(
  folderId: string,
  data: { name?: string; lot?: string; phase?: string },
): Promise<Result<Folder>> {
  return attempt(() => apiPatch<Folder>(`/folders/${folderId}`, data));
}

/**
 * Deletes a folder. Documents in it are moved to root.
 */
export function deleteFolder(folderId: string): Promise<Result<void>> {
  return attempt(() => apiDelete(`/folders/${folderId}`));
}
