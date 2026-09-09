import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { SlidePanel } from "@/components/ui/SlidePanel";
import type { ReadOnlyRef } from "@/hooks/useModalDialog";
import { useChunkDetail, useSimilarChunks } from "../hooks/hooks";
import { useChunkDetailActions } from "../hooks/useChunkDetailActions";
import { useAdminStore } from "../stores/store";
import { ChunkDetailActionBar } from "./ChunkDetailActionBar";
import { ChunkDetailDisplay } from "./ChunkDetailDisplay";
import { ChunkDetailRelatedChunks } from "./ChunkDetailRelatedChunks";
import { ChunkDetailTextPanel } from "./ChunkDetailTextPanel";

interface ChunkDetailProps {
  projectId: string;
  /**
   * Where focus lands when the panel closes and the card that opened it is
   * gone — which is the common case: deleting, splitting or merging a chunk
   * closes the panel and invalidates the list, unmounting that very card.
   */
  fallbackFocusRef?: ReadOnlyRef;
}

export function ChunkDetail({ projectId, fallbackFocusRef }: ChunkDetailProps) {
  const selectedChunkId = useAdminStore((s) => s.selectedChunkId);
  const selectChunk = useAdminStore((s) => s.selectChunk);
  const {
    data: chunk,
    isPending,
    error: chunkError,
  } = useChunkDetail(projectId, selectedChunkId);
  const { data: similarChunks, error: similarError } = useSimilarChunks(
    projectId,
    selectedChunkId,
  );

  const {
    isEditing,
    setIsEditing,
    editText,
    setEditText,
    textareaRef,
    showDeleteConfirm,
    setShowDeleteConfirm,
    isMutating,
    actionError,
    updateMutation,
    splitMutation,
    mergeMutation,
    deleteMutation,
    handleStartEdit,
    handleCancelEdit,
    handleSave,
    handleSplit,
    handleMerge,
    handleDelete,
  } = useChunkDetailActions(projectId, selectedChunkId, selectChunk, chunk);

  return (
    <SlidePanel
      isOpen={!!selectedChunkId}
      onClose={() => {
        selectChunk(null);
        setIsEditing(false);
      }}
      title="Détail du chunk"
      width="w-[520px]"
      fallbackFocusRef={fallbackFocusRef}
    >
      {isPending ? (
        <div className="space-y-4">
          <Skeleton variant="rectangular" className="h-8" />
          <Skeleton variant="rectangular" className="h-48" />
          <Skeleton variant="rectangular" className="h-32" />
        </div>
      ) : chunk ? (
        <div className="space-y-5">
          {chunkError && <ErrorMessage error={chunkError} />}
          {actionError && <ErrorMessage error={actionError} />}

          <ChunkDetailActionBar
            isEditing={isEditing}
            isMutating={isMutating}
            isSaving={updateMutation.isPending}
            isSplitting={splitMutation.isPending}
            isDeleting={deleteMutation.isPending}
            canSave={!!editText.trim()}
            showDeleteConfirm={showDeleteConfirm}
            onStartEdit={handleStartEdit}
            onSave={handleSave}
            onSplit={handleSplit}
            onCancelEdit={handleCancelEdit}
            onShowDeleteConfirmChange={setShowDeleteConfirm}
            onDelete={handleDelete}
          />

          <ChunkDetailDisplay chunk={chunk} />

          <ChunkDetailTextPanel
            chunk={chunk}
            isEditing={isEditing}
            editText={editText}
            onEditTextChange={setEditText}
            textareaRef={textareaRef}
          />

          <ChunkDetailRelatedChunks
            chunk={chunk}
            similarChunks={similarChunks}
            similarError={similarError}
            mergeError={mergeMutation.error}
            isMutating={isMutating}
            onSelectChunk={selectChunk}
            onMerge={handleMerge}
          />
        </div>
      ) : chunkError ? (
        <ErrorMessage error={chunkError} />
      ) : (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">Chunk introuvable.</p>
      )}
    </SlidePanel>
  );
}
