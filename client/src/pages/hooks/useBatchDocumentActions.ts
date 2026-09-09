import { useCallback } from "react";
import type { useDeleteDocument, useMoveDocument } from "@/features/projects";

interface UseBatchDocumentActionsArgs {
  selectedIds: Set<string>;
  deleteDoc: ReturnType<typeof useDeleteDocument>;
  moveDocMut: ReturnType<typeof useMoveDocument>;
  clear: () => void;
}

interface BatchDocumentActions {
  handleMoveDocument: (documentId: string, folderId: string | null) => void;
  handleBatchDelete: () => void;
  handleBatchMove: (folderId: string | null) => void;
}

/**
 * Batch move/delete handlers. `handleBatchDelete` waits for every deletion to
 * settle before clearing the selection; `handleBatchMove` clears immediately
 * — two different behaviours today, both preserved as-is.
 */
export function useBatchDocumentActions({
  selectedIds,
  deleteDoc,
  moveDocMut,
  clear,
}: UseBatchDocumentActionsArgs): BatchDocumentActions {
  const handleMoveDocument = useCallback(
    (documentId: string, folderId: string | null): void => {
      moveDocMut.mutate({ documentId, folderId });
    },
    [moveDocMut],
  );

  const handleBatchDelete = useCallback((): void => {
    const ids = Array.from(selectedIds);
    Promise.allSettled(
      ids.map(
        (id) =>
          new Promise<void>((resolve, reject) => {
            deleteDoc.mutate(id, {
              onSuccess: () => resolve(),
              onError: (err) => reject(err),
            });
          }),
      ),
    ).then(() => {
      clear();
    });
  }, [selectedIds, deleteDoc, clear]);

  const handleBatchMove = useCallback(
    (folderId: string | null): void => {
      const ids = Array.from(selectedIds);
      for (const id of ids) {
        moveDocMut.mutate({ documentId: id, folderId });
      }
      clear();
    },
    [selectedIds, moveDocMut, clear],
  );

  return { handleMoveDocument, handleBatchDelete, handleBatchMove };
}
