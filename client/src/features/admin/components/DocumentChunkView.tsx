import { useEffect, useState } from "react";
import { useDocumentChunks, useRechunkDocument } from "../hooks/hooks";
import { useAdminStore } from "../stores/store";
import type { ChunkStatsResponse, RechunkResponse } from "../types/types";
import { DocumentChunkViewList } from "./DocumentChunkViewList";
import { DocumentChunkViewRechunkPanel } from "./DocumentChunkViewRechunkPanel";
import { DocumentChunkViewToolbar } from "./DocumentChunkViewToolbar";
import { DuplicateDetection } from "./DuplicateDetection";

interface DocumentChunkViewProps {
  projectId: string;
  stats: ChunkStatsResponse | undefined;
}

export function DocumentChunkView({
  projectId,
  stats,
}: DocumentChunkViewProps): React.ReactElement {
  const selectedDocumentId = useAdminStore((s) => s.selectedDocumentId);
  const setSelectedDocument = useAdminStore((s) => s.setSelectedDocument);
  const selectChunk = useAdminStore((s) => s.selectChunk);
  const claimActionFailure = useAdminStore((s) => s.claimActionFailure);
  const releaseActionFailure = useAdminStore((s) => s.releaseActionFailure);
  const {
    data: chunks,
    isPending,
    error,
  } = useDocumentChunks(projectId, selectedDocumentId);
  const rechunkMutation = useRechunkDocument(projectId);
  const [showDuplicates, setShowDuplicates] = useState(false);
  const [showRechunkConfirm, setShowRechunkConfirm] = useState(false);
  const [rechunkResult, setRechunkResult] = useState<RechunkResponse | null>(null);

  const documents = stats?.by_document ?? [];
  const rechunkError = rechunkMutation.error;

  /**
   * `useRechunkDocument` reports every failure to the store so it outlives this
   * view — switching tab mid-run used to lose it. While the view says it itself,
   * claim it; the release hands it back to the banner instead of losing it.
   */
  useEffect(() => {
    if (!rechunkError) return;
    claimActionFailure();
    return releaseActionFailure;
  }, [rechunkError, claimActionFailure, releaseActionFailure]);

  function handleSelectDocument(id: string | null): void {
    setSelectedDocument(id);
    setShowDuplicates(false);
    setShowRechunkConfirm(false);
    setRechunkResult(null);
    rechunkMutation.reset();
  }

  function handleRechunkClick(): void {
    rechunkMutation.reset();
    setRechunkResult(null);
    setShowRechunkConfirm(true);
  }

  function handleConfirmRechunk(): void {
    if (!selectedDocumentId) return;
    setRechunkResult(null);
    rechunkMutation.mutate(selectedDocumentId, {
      onSuccess: (result) => {
        setRechunkResult(result);
        setShowRechunkConfirm(false);
      },
    });
  }

  return (
    <div className="space-y-4">
      <DocumentChunkViewToolbar
        documents={documents}
        selectedDocumentId={selectedDocumentId}
        onSelectDocument={handleSelectDocument}
        onRechunkClick={handleRechunkClick}
        isRechunkPending={rechunkMutation.isPending}
        showDuplicates={showDuplicates}
        onToggleDuplicates={() => setShowDuplicates(!showDuplicates)}
      />

      {!selectedDocumentId && (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          Sélectionnez un document pour voir ses chunks dans l'ordre.
        </p>
      )}

      <DocumentChunkViewRechunkPanel
        show={showRechunkConfirm && !!selectedDocumentId}
        onConfirm={handleConfirmRechunk}
        onCancel={() => setShowRechunkConfirm(false)}
        isPending={rechunkMutation.isPending}
        error={rechunkMutation.error}
        result={rechunkResult}
        onDismissResult={() => setRechunkResult(null)}
      />

      {showDuplicates && selectedDocumentId && (
        <DuplicateDetection projectId={projectId} documentId={selectedDocumentId} />
      )}

      <DocumentChunkViewList
        isPending={isPending && !!selectedDocumentId}
        error={error}
        chunks={chunks}
        onSelectChunk={selectChunk}
      />
    </div>
  );
}
