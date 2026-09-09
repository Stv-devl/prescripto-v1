import { create } from "zustand";
import { registerSessionReset } from "@/lib/store/sessionReset";

type UploadStatus = "uploading" | "processing" | "ready" | "error";

interface UploadEntry {
  fileName: string;
  progress: number;
  status: UploadStatus;
  folderId: string | null;
  resolvedDocId: string | null;
}

interface UploadState {
  uploads: Record<string, UploadEntry>;
  uploadingFolderIds: Set<string>;
  addUpload: (id: string, fileName: string, folderId?: string | null) => void;
  setProgress: (id: string, progress: number) => void;
  setStatus: (id: string, status: UploadStatus) => void;
  setResolved: (id: string, docId: string) => void;
  removeUpload: (id: string) => void;
  addUploadingFolder: (folderId: string) => void;
  removeUploadingFolder: (folderId: string) => void;
  reset: () => void;
}

/**
 * Tracks ongoing file uploads with progress and status.
 * Keyed by a unique upload ID (typically crypto.randomUUID()).
 */
export const useUploadStore = create<UploadState>((set) => ({
  uploads: {},
  uploadingFolderIds: new Set(),

  addUpload: (id, fileName, folderId = null) =>
    set((state) => ({
      uploads: {
        ...state.uploads,
        [id]: { fileName, progress: 0, status: "uploading", folderId, resolvedDocId: null },
      },
    })),

  setProgress: (id, progress) =>
    set((state) => {
      const entry = state.uploads[id];
      if (!entry) return state;
      return {
        uploads: { ...state.uploads, [id]: { ...entry, progress } },
      };
    }),

  setStatus: (id, status) =>
    set((state) => {
      const entry = state.uploads[id];
      if (!entry) return state;
      return {
        uploads: { ...state.uploads, [id]: { ...entry, status } },
      };
    }),

  setResolved: (id, docId) =>
    set((state) => {
      const entry = state.uploads[id];
      if (!entry) return state;
      return {
        uploads: { ...state.uploads, [id]: { ...entry, resolvedDocId: docId } },
      };
    }),

  removeUpload: (id) =>
    set((state) => {
      const { [id]: _, ...rest } = state.uploads;
      return { uploads: rest };
    }),

  addUploadingFolder: (folderId) =>
    set((state) => {
      const next = new Set(state.uploadingFolderIds);
      next.add(folderId);
      return { uploadingFolderIds: next };
    }),

  removeUploadingFolder: (folderId) =>
    set((state) => {
      const next = new Set(state.uploadingFolderIds);
      next.delete(folderId);
      return { uploadingFolderIds: next };
    }),

  reset: () => set({ uploads: {}, uploadingFolderIds: new Set<string>() }),
}));

registerSessionReset(() => useUploadStore.getState().reset());
