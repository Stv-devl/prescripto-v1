import type { useDeleteChunk, useMergeChunks } from "./hooks";

interface UseChunkDetailMergeAndDeleteArgs {
  selectedChunkId: string | null;
  selectChunk: (id: string | null) => void;
  setShowDeleteConfirm: (show: boolean) => void;
  clearActionError: () => void;
  mergeMutation: ReturnType<typeof useMergeChunks>;
  deleteMutation: ReturnType<typeof useDeleteChunk>;
}

/** `handleMerge` and `handleDelete` — the two mutations that act on the chunk itself. */
export function useChunkDetailMergeAndDelete({
  selectedChunkId,
  selectChunk,
  setShowDeleteConfirm,
  clearActionError,
  mergeMutation,
  deleteMutation,
}: UseChunkDetailMergeAndDeleteArgs): {
  handleMerge: (adjacentId: string) => void;
  handleDelete: () => void;
} {
  function handleMerge(adjacentId: string): void {
    if (!selectedChunkId) return;
    clearActionError();
    mergeMutation.mutate(
      { chunkId: selectedChunkId, body: { adjacent_chunk_id: adjacentId } },
      { onSuccess: () => selectChunk(null) },
    );
  }

  function handleDelete(): void {
    if (!selectedChunkId) return;
    clearActionError();
    deleteMutation.mutate(selectedChunkId, {
      onSuccess: () => {
        selectChunk(null);
        setShowDeleteConfirm(false);
      },
    });
  }

  return { handleMerge, handleDelete };
}
