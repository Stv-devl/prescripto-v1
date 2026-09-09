import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import type { RechunkResponse } from "../types/types";

interface DocumentChunkViewRechunkPanelProps {
  show: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
  error: Error | null;
  result: RechunkResponse | null;
  onDismissResult: () => void;
}

/** Confirmation, error and result of `DocumentChunkView`'s re-chunk workflow. */
export function DocumentChunkViewRechunkPanel({
  show,
  onConfirm,
  onCancel,
  isPending,
  error,
  result,
  onDismissResult,
}: DocumentChunkViewRechunkPanelProps): React.ReactElement {
  return (
    <>
      {show && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="mb-3 text-sm text-amber-400">
            Re-chunker supprimera tous les chunks existants et relancera le pipeline d'ingestion. Continuer ?
          </p>
          <div className="flex gap-2">
            <button
              onClick={onConfirm}
              disabled={isPending}
              className="rounded-md bg-amber-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50"
            >
              {isPending ? "En cours..." : "Confirmer"}
            </button>
            <button
              onClick={onCancel}
              className="rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {error && <ErrorMessage error={error} />}

      {result && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
          <p className="mb-1 text-sm font-medium text-emerald-400">Re-chunking terminé</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-emerald-300">
            <span>Avant : {result.old_count} chunks ({Math.round(result.old_avg_chars)} chars moy.)</span>
            <span>Après : {result.new_count} chunks ({Math.round(result.new_avg_chars)} chars moy.)</span>
          </div>
          <button onClick={onDismissResult} className="mt-2 text-xs text-emerald-400 underline">
            Fermer
          </button>
        </div>
      )}
    </>
  );
}
