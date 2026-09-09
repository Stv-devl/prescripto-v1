import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import { listDocuments, deleteDocument, moveDocument } from "../services/projects.service";

/**
 * Fetches documents for a project.
 * Polls every 5s if any document is still processing.
 */
export function useDocuments(projectId: string) {
  return useQuery({
    queryKey: ["documents", projectId],
    queryFn: async () => unwrap(await listDocuments(projectId)),
    enabled: !!projectId,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasProcessing = data?.documents.some(
        (d) => d.status === "processing" || d.status === "uploading",
      );
      return hasProcessing ? 5000 : false;
    },
  });
}

/**
 * Deletes a document and invalidates the documents list.
 */
export function useDeleteDocument(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: string) =>
      unwrap(await deleteDocument(documentId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
    },
  });
}

/**
 * Moves a document to a folder (or to root) and invalidates documents + folders.
 */
export function useMoveDocument(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      documentId,
      folderId,
    }: {
      documentId: string;
      folderId: string | null;
    }) => unwrap(await moveDocument(documentId, folderId)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
    },
  });
}
