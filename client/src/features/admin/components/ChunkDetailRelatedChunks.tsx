import { ChevronLeft, ChevronRight, Merge } from "lucide-react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { cn } from "@/lib/utils";
import type { ChunkDetail, SimilarChunkResult } from "../types/types";
import { CONTENT_TYPE_BADGES } from "./chunkContentTypeBadges";

interface ChunkDetailRelatedChunksProps {
  chunk: ChunkDetail;
  similarChunks: SimilarChunkResult[] | undefined;
  similarError: Error | null;
  mergeError: Error | null;
  isMutating: boolean;
  onSelectChunk: (id: string) => void;
  onMerge: (adjacentId: string) => void;
}

export function ChunkDetailRelatedChunks({
  chunk,
  similarChunks,
  similarError,
  mergeError,
  isMutating,
  onSelectChunk,
  onMerge,
}: ChunkDetailRelatedChunksProps) {
  return (
    <>
      {chunk.adjacent_chunks.length > 0 && (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Chunks adjacents
          </h3>
          <div className="space-y-2">
            {chunk.adjacent_chunks.map((adj) => (
              <div
                key={adj.id}
                className="flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] p-3"
              >
                <button
                  onClick={() => onSelectChunk(adj.id)}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm transition-colors hover:text-[#FFC300]"
                >
                  {adj.position < chunk.position ? (
                    <ChevronLeft className="h-4 w-4 shrink-0 text-[hsl(var(--muted-foreground))]" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0 text-[hsl(var(--muted-foreground))]" />
                  )}
                  <div className="min-w-0 flex-1">
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      pos.{adj.position} — p.{adj.page}
                    </span>
                    <p className="truncate text-[hsl(var(--foreground))]">{adj.text_preview}</p>
                  </div>
                </button>
                <button
                  onClick={() => onMerge(adj.id)}
                  disabled={isMutating}
                  title={`Fusionner avec chunk #${adj.position}`}
                  className="shrink-0 rounded-md border border-[hsl(var(--border))] p-1.5 text-[hsl(var(--muted-foreground))] transition-colors hover:border-blue-500/50 hover:text-blue-400 disabled:opacity-50"
                >
                  <Merge className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
          {mergeError && (
            <div className="mt-2">
              <ErrorMessage error={mergeError} inline />
            </div>
          )}
        </section>
      )}
      {(similarError || (similarChunks && similarChunks.length > 0)) && (
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Chunks similaires
          </h3>
          {similarError && <ErrorMessage error={similarError} inline />}
          <div className="space-y-2">
            {similarChunks?.map((sim) => (
              <button
                key={sim.chunk_id}
                onClick={() => onSelectChunk(sim.chunk_id)}
                className="flex w-full items-center gap-3 rounded-lg border border-[hsl(var(--border))] p-3 text-left transition-colors hover:bg-[hsl(var(--muted))]"
              >
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                    <span className="font-medium text-[hsl(var(--foreground))]">{sim.filename}</span>
                    {sim.content_type && (
                      <span className={cn(
                        "rounded-full px-2 py-0.5 font-medium",
                        CONTENT_TYPE_BADGES[sim.content_type] ?? "bg-slate-500/15 text-slate-400",
                      )}>
                        {sim.content_type}
                      </span>
                    )}
                  </div>
                  <p className="truncate text-sm text-[hsl(var(--foreground))]">{sim.text_preview}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-0.5">
                  <span className="text-xs font-medium text-[#FFC300]">
                    {Math.round(sim.similarity * 100)}%
                  </span>
                  <div className="h-1.5 w-10 rounded-full bg-[hsl(var(--muted))]">
                    <div
                      className="h-full rounded-full bg-[#FFC300]"
                      style={{ width: `${Math.round(sim.similarity * 100)}%` }}
                    />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
