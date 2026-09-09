import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ServiceFailure, unwrap } from "@/lib/result";
import { beginSessionScope } from "@/lib/store/sessionReset";
import {
  uploadDocumentWithProgress,
  uploadDocumentToFolder,
  createFolder,
} from "../services/projects.service";
import { useUploadStore } from "../stores/uploadStore";
import type { FolderList } from "../types/types";

/**
 * Uploads a document with progress tracking and invalidates the documents list.
 * Updates the upload store with progress and status throughout the upload lifecycle.
 */
export function useUploadDocument(projectId: string) {
  const queryClient = useQueryClient();
  const { addUpload, setProgress, setStatus, setResolved, removeUpload } =
    useUploadStore();

  return useMutation({
    mutationFn: async ({
      file,
      uploadId,
    }: {
      file: File;
      uploadId: string;
    }) => {
      addUpload(uploadId, file.name);
      return unwrap(
        await uploadDocumentWithProgress(projectId, file, (percent) => {
          setProgress(uploadId, percent);
        }),
      );
    },
    onSuccess: (doc, { uploadId }) => {
      setStatus(uploadId, "processing");
      setResolved(uploadId, doc.id);
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      setTimeout(() => removeUpload(uploadId), 3000);
    },
    onError: (_error, { uploadId }) => {
      setStatus(uploadId, "error");
      setTimeout(() => removeUpload(uploadId), 5000);
    },
  });
}

/**
 * Uploads a folder: creates a Prescripto folder, then uploads all files into it.
 * Tracks each file's progress individually via the upload store.
 */
export function useUploadFolder(projectId: string) {
  const queryClient = useQueryClient();
  const {
    addUpload,
    setProgress,
    setStatus,
    setResolved,
    removeUpload,
    addUploadingFolder,
    removeUploadingFolder,
  } = useUploadStore();

  return useMutation({
    mutationFn: async ({
      folderName,
      files,
    }: {
      folderName: string;
      files: File[];
    }) => {
      const inSession = beginSessionScope();
      const folder = unwrap(
        await createFolder(projectId, {
          name: folderName,
          lot: "",
          phase: "",
        }),
      );

      inSession(() => {
        queryClient.setQueryData<FolderList>(["folders", projectId], (old) => {
          if (!old) return { folders: [folder], total: 1 };
          const exists = old.folders.some((f) => f.id === folder.id);
          if (exists) return old;
          return {
            folders: [...old.folders, folder],
            total: old.total + 1,
          };
        });
        addUploadingFolder(folder.id);
      });

      const results = await Promise.allSettled(
        files.map((file) => {
          const uploadId = crypto.randomUUID();
          inSession(() => addUpload(uploadId, file.name, folder.id));
          return uploadDocumentToFolder(
            projectId,
            file,
            folder.id,
            (percent) => {
              setProgress(uploadId, percent);
            },
          ).then((result) => {
            if (!result.success) {
              setStatus(uploadId, "error");
              setTimeout(() => removeUpload(uploadId), 5000);
              throw new ServiceFailure(result.error);
            }
            setStatus(uploadId, "processing");
            setResolved(uploadId, result.data.id);
            queryClient.invalidateQueries({
              queryKey: ["documents", projectId],
            });
            return result.data;
          });
        }),
      );

      removeUploadingFolder(folder.id);
      return results;
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
    },
  });
}

/**
 * Uploads a single document to a specific folder with progress tracking.
 * Invalidates both documents and folders lists on completion.
 */
export function useUploadDocumentToFolder(projectId: string) {
  const queryClient = useQueryClient();
  const { addUpload, setProgress, setStatus, setResolved, removeUpload } =
    useUploadStore();

  return useMutation({
    mutationFn: async ({
      file,
      uploadId,
      folderId,
    }: {
      file: File;
      uploadId: string;
      folderId: string;
    }) => {
      addUpload(uploadId, file.name, folderId);
      return unwrap(
        await uploadDocumentToFolder(projectId, file, folderId, (percent) => {
          setProgress(uploadId, percent);
        }),
      );
    },
    onSuccess: (doc, { uploadId }) => {
      setStatus(uploadId, "processing");
      setResolved(uploadId, doc.id);
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      queryClient.invalidateQueries({ queryKey: ["folders", projectId] });
      setTimeout(() => removeUpload(uploadId), 3000);
    },
    onError: (_error, { uploadId }) => {
      setStatus(uploadId, "error");
      setTimeout(() => removeUpload(uploadId), 5000);
    },
  });
}
