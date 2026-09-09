import { create } from "zustand";
import { registerSessionReset } from "@/lib/store/sessionReset";

interface PendingFolderUpload {
  folderName: string;
  files: File[];
}

interface PendingFolderUploadState {
  pending: PendingFolderUpload | null;
  setPending: (data: PendingFolderUpload) => void;
  consume: () => PendingFolderUpload | null;
  reset: () => void;
}

/**
 * Transient store that holds files from a dropped folder on the projects list page.
 * Consumed once by ProjectWorkspacePage after navigation to trigger the upload.
 */
export const usePendingFolderUploadStore = create<PendingFolderUploadState>(
  (set, get) => ({
    pending: null,
    setPending: (data) => set({ pending: data }),
    consume: () => {
      const current = get().pending;
      if (current) set({ pending: null });
      return current;
    },
    reset: () => set({ pending: null }),
  }),
);

registerSessionReset(() => usePendingFolderUploadStore.getState().reset());
