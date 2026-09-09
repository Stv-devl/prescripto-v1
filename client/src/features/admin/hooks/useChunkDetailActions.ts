import type { ChunkDetail } from "../types/types";
import {
  useDeleteChunk,
  useMergeChunks,
  useSplitChunk,
  useUpdateChunk,
} from "./hooks";
import { useChunkDetailEditState } from "./useChunkDetailEditState";
import { useChunkDetailMergeAndDelete } from "./useChunkDetailMergeAndDelete";
import { useChunkDetailMutations } from "./useChunkDetailMutations";
import { useChunkDetailSaveAndSplit } from "./useChunkDetailSaveAndSplit";

interface ChunkDetailActions {
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editText: string;
  setEditText: (text: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  showDeleteConfirm: boolean;
  setShowDeleteConfirm: (show: boolean) => void;
  isMutating: boolean;
  actionError: Error | null;
  updateMutation: ReturnType<typeof useUpdateChunk>;
  splitMutation: ReturnType<typeof useSplitChunk>;
  mergeMutation: ReturnType<typeof useMergeChunks>;
  deleteMutation: ReturnType<typeof useDeleteChunk>;
  handleStartEdit: () => void;
  handleCancelEdit: () => void;
  handleSave: () => void;
  handleSplit: () => void;
  handleMerge: (adjacentId: string) => void;
  handleDelete: () => void;
}

/**
 * Composes `ChunkDetail`'s edit-lifecycle and mutation state into the six
 * handlers its action bar and related-chunks list call.
 */
export function useChunkDetailActions(
  projectId: string,
  selectedChunkId: string | null,
  selectChunk: (id: string | null) => void,
  chunk: ChunkDetail | undefined,
): ChunkDetailActions {
  const editState = useChunkDetailEditState();
  const mutations = useChunkDetailMutations(projectId);
  const { editText, setEditText, setIsEditing, setShowDeleteConfirm, textareaRef } = editState;
  const { updateMutation, splitMutation, mergeMutation, deleteMutation, clearActionError } =
    mutations;

  function handleStartEdit(): void {
    if (chunk) {
      setEditText(chunk.text);
      setIsEditing(true);
    }
  }

  function handleCancelEdit(): void {
    setIsEditing(false);
    setEditText("");
  }

  const { handleSave, handleSplit } = useChunkDetailSaveAndSplit({
    selectedChunkId,
    selectChunk,
    editText,
    textareaRef,
    setIsEditing,
    clearActionError,
    updateMutation,
    splitMutation,
  });

  const { handleMerge, handleDelete } = useChunkDetailMergeAndDelete({
    selectedChunkId,
    selectChunk,
    setShowDeleteConfirm,
    clearActionError,
    mergeMutation,
    deleteMutation,
  });

  return {
    ...editState,
    ...mutations,
    handleStartEdit,
    handleCancelEdit,
    handleSave,
    handleSplit,
    handleMerge,
    handleDelete,
  };
}
