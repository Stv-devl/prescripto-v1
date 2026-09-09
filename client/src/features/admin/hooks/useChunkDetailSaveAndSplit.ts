import type { RefObject } from "react";
import type { useSplitChunk, useUpdateChunk } from "./hooks";

interface UseChunkDetailSaveAndSplitArgs {
  selectedChunkId: string | null;
  selectChunk: (id: string | null) => void;
  editText: string;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  setIsEditing: (editing: boolean) => void;
  clearActionError: () => void;
  updateMutation: ReturnType<typeof useUpdateChunk>;
  splitMutation: ReturnType<typeof useSplitChunk>;
}

/** `handleSave` and `handleSplit` — the two mutations reading the in-progress edit. */
export function useChunkDetailSaveAndSplit({
  selectedChunkId,
  selectChunk,
  editText,
  textareaRef,
  setIsEditing,
  clearActionError,
  updateMutation,
  splitMutation,
}: UseChunkDetailSaveAndSplitArgs): {
  handleSave: () => void;
  handleSplit: () => void;
} {
  function handleSave(): void {
    if (!selectedChunkId || !editText.trim()) return;
    clearActionError();
    updateMutation.mutate(
      { chunkId: selectedChunkId, body: { text: editText.trim() } },
      { onSuccess: () => setIsEditing(false) },
    );
  }

  function handleSplit(): void {
    if (!selectedChunkId || !textareaRef.current) return;
    const pos = textareaRef.current.selectionStart;
    if (pos <= 0 || pos >= editText.length) return;
    clearActionError();
    splitMutation.mutate(
      { chunkId: selectedChunkId, body: { split_position: pos } },
      {
        onSuccess: () => {
          setIsEditing(false);
          selectChunk(null);
        },
      },
    );
  }

  return { handleSave, handleSplit };
}
