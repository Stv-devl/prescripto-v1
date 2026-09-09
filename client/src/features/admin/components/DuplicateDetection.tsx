import { AlertTriangle, Copy } from "lucide-react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useDuplicates } from "../hooks/hooks";
import { useAdminStore } from "../stores/store";

interface DuplicateDetectionProps {
  projectId: string;
  documentId: string;
}

export function DuplicateDetection({ projectId, documentId }: DuplicateDetectionProps) {
  const { data, isPending, error } = useDuplicates(projectId, documentId);
  const { selectChunk, setActiveTab } = useAdminStore();

  function handleNavigate(chunkId: string): void {
    selectChunk(chunkId);
    setActiveTab("table");
  }

  if (isPending) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" className="h-24" />
        ))}
      </div>
    );
  }

  if (error && !data) {
    return <ErrorMessage error={error} />;
  }

  if (!data) return null;

  return (
    <section className="space-y-4">
      {error && <ErrorMessage error={error} />}

      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[hsl(var(--foreground))]">
          <Copy className="h-4 w-4 text-[#FFC300]" />
          Doublons détectés
        </h2>
        <span className="text-xs text-[hsl(var(--muted-foreground))]">
          {data.total_chunks_analyzed} chunks analysés
        </span>
      </div>

      {!error && data.pairs.length === 0 && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-400">
          Aucun doublon détecté (seuil : 92%).
        </div>
      )}

      {data.pairs.map((pair, index) => (
        <article
          key={`${pair.chunk_a_id}-${pair.chunk_b_id}`}
          className="rounded-lg border border-amber-500/30 bg-[hsl(var(--secondary))]/30 p-4"
        >
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <span className="text-xs font-medium text-amber-400">
              Paire #{index + 1} — Similarité : {Math.round(pair.similarity * 100)}%
            </span>
            <div className="ml-auto h-2 w-20 rounded-full bg-[hsl(var(--muted))]">
              <div
                className="h-full rounded-full bg-amber-500"
                style={{ width: `${Math.round(pair.similarity * 100)}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleNavigate(pair.chunk_a_id)}
              className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 text-left transition-colors hover:border-[#FFC300]/50"
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                <span className="rounded bg-[#FFC300]/15 px-1.5 py-0.5 font-medium text-[#FFC300]">
                  #{pair.chunk_a_position}
                </span>
                <span>p.{pair.chunk_a_page}</span>
              </div>
              <p className="text-xs leading-relaxed text-[hsl(var(--foreground))]">
                {pair.chunk_a_preview}
              </p>
            </button>

            <button
              onClick={() => handleNavigate(pair.chunk_b_id)}
              className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 text-left transition-colors hover:border-[#FFC300]/50"
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                <span className="rounded bg-[#FFC300]/15 px-1.5 py-0.5 font-medium text-[#FFC300]">
                  #{pair.chunk_b_position}
                </span>
                <span>p.{pair.chunk_b_page}</span>
              </div>
              <p className="text-xs leading-relaxed text-[hsl(var(--foreground))]">
                {pair.chunk_b_preview}
              </p>
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
