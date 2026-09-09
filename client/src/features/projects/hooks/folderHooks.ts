import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import {
  listFolders,
  createFolder,
  updateFolder,
  deleteFolder,
} from "../services/projects.service";
import type { CreateFolderInput } from "../types/types";

/**
 * Fetches folders for a project.
 */
export function useFolders(projectId: string) {
  return useQuery({
    queryKey: ["folders", projectId],
    queryFn: async () => unwrap(await listFolders(projectId)),
    enabled: !!projectId,
  });
}

/**
 * Creates a folder and invalidates the folders list.
 */
export function useCreateFolder(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateFolderInput) =>
      unwrap(await createFolder(projectId, data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
    },
  });
}

/**
 * Updates a folder (name, lot, phase) and invalidates the folders list.
 */
export function useUpdateFolder(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      folderId,
      ...data
    }: {
      folderId: string;
      name?: string;
      lot?: string;
      phase?: string;
    }) => unwrap(await updateFolder(folderId, data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
    },
  });
}

/**
 * Deletes a folder and invalidates folders + documents lists.
 */
export function useDeleteFolder(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (folderId: string) =>
      unwrap(await deleteFolder(folderId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}
