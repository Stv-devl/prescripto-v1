import { useEffect } from "react";
import { useAdminStore } from "../stores/store";
import {
  useDeleteChunk,
  useMergeChunks,
  useSplitChunk,
  useUpdateChunk,
} from "./hooks";

interface ChunkDetailMutations {
  updateMutation: ReturnType<typeof useUpdateChunk>;
  splitMutation: ReturnType<typeof useSplitChunk>;
  mergeMutation: ReturnType<typeof useMergeChunks>;
  deleteMutation: ReturnType<typeof useDeleteChunk>;
  isMutating: boolean;
  actionError: Error | null;
  clearActionError: () => void;
}

/**
 * `ChunkDetail`'s four mutations, their aggregate pending/error state, and
 * the claim/release of the global action-failure banner while this panel
 * shows the error itself.
 */
export function useChunkDetailMutations(projectId: string): ChunkDetailMutations {
  const claimActionFailure = useAdminStore((s) => s.claimActionFailure);
  const releaseActionFailure = useAdminStore((s) => s.releaseActionFailure);

  const updateMutation = useUpdateChunk(projectId);
  const splitMutation = useSplitChunk(projectId);
  const mergeMutation = useMergeChunks(projectId);
  const deleteMutation = useDeleteChunk(projectId);

  const isMutating =
    updateMutation.isPending ||
    splitMutation.isPending ||
    mergeMutation.isPending ||
    deleteMutation.isPending;

  const actionError =
    updateMutation.error ?? splitMutation.error ?? deleteMutation.error;
  const shownHere = actionError ?? mergeMutation.error;

  useEffect(() => {
    if (!shownHere) return;
    claimActionFailure();
    return releaseActionFailure;
  }, [shownHere, claimActionFailure, releaseActionFailure]);

  function clearActionError(): void {
    updateMutation.reset();
    splitMutation.reset();
    mergeMutation.reset();
    deleteMutation.reset();
  }

  return {
    updateMutation,
    splitMutation,
    mergeMutation,
    deleteMutation,
    isMutating,
    actionError,
    clearActionError,
  };
}
