import { AlertTriangle } from "lucide-react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { cn } from "@/lib/utils";
import type { ChunkListItem } from "../types/types";
import { findOverlap, hasGap } from "../utils/chunkGapOverlap.utils";
import { CONTENT_TYPE_BADGES } from "./chunkContentTypeBadges";

interface DocumentChunkViewListProps {
  isPending: boolean;
  error: Error | null;
  chunks: ChunkListItem[] | undefined;
  onSelectChunk: (id: string) => void;
}

/**
 * The three React Query states of the selected document's chunks, plus the
 * chunk list itself with gap/overlap indicators between consecutive chunks.
 * `isPending` here is expected already composed with a document-selected
 * guard by the caller — see `DocumentChunkView.tsx`.
 */
export function DocumentChunkViewList({
  isPending,
  error,
  chunks,
  onSelectChunk,
}: DocumentChunkViewListProps): React.ReactElement {
  return (
    <>
      {isPending && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} variant="rectangular" className="h-28" />
          ))}
        </div>
      )}

      {error && <ErrorMessage error={error} />}

      {!error && chunks && chunks.length === 0 && (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">Aucun chunk pour ce document.</p>
      )}

      {chunks && chunks.length > 0 && (
        <div className="space-y-1">
          {chunks.map((chunk, index) => {
            const isSmall = chunk.char_count !== null && chunk.char_count < 100;
            const isLarge = chunk.char_count !== null && chunk.char_count >= 2500;
            const prev = index > 0 ? chunks[index - 1] : null;
            const gap = prev ? hasGap(chunk, prev) : false;
            const overlap = prev ? findOverlap(prev.text_preview, chunk.text_preview) : "";

            return (
              <div key={chunk.id}>
                {gap && (
                  <div className="flex items-center gap-2 py-2">
                    <div className="h-px flex-1 border-t border-dashed border-amber-500/50" />
                    <span className="flex items-center gap-1 text-xs text-amber-400">
                      <AlertTriangle className="h-3 w-3" />
                      Gap détecté (p.{prev?.page} → p.{chunk.page})
                    </span>
                    <div className="h-px flex-1 border-t border-dashed border-amber-500/50" />
                  </div>
                )}

                {overlap.length > 20 && !gap && (
                  <div className="mx-4 my-1 rounded border border-slate-500/20 bg-slate-500/5 px-3 py-1.5">
                    <span className="text-xs text-slate-400">Overlap ({overlap.length} chars) :</span>
                    <p className="mt-0.5 text-xs italic text-slate-500 line-clamp-2">{overlap}</p>
                  </div>
                )}

                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectChunk(chunk.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectChunk(chunk.id);
                    }
                  }}
                  className={cn(
                    "cursor-pointer rounded-lg border bg-[hsl(var(--secondary))]/30 p-4 transition-colors hover:bg-[hsl(var(--muted))]",
                    isSmall
                      ? "border-amber-500/40"
                      : isLarge
                        ? "border-red-500/40"
                        : "border-[hsl(var(--border))]",
                  )}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span className="rounded-full bg-[#FFC300]/15 px-2.5 py-0.5 text-xs font-medium text-[#FFC300]">
                      #{chunk.position}
                    </span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">p.{chunk.page}</span>
                    {chunk.content_type && (
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-0.5 text-xs font-medium",
                          CONTENT_TYPE_BADGES[chunk.content_type] ?? "bg-slate-500/15 text-slate-400",
                        )}
                      >
                        {chunk.content_type}
                      </span>
                    )}
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">{chunk.char_count} chars</span>
                    {chunk.quality_score != null && (
                      <span
                        className={cn(
                          "ml-auto rounded-full px-2 py-0.5 text-xs font-medium text-white",
                          chunk.quality_score >= 0.7
                            ? "bg-emerald-500"
                            : chunk.quality_score >= 0.4
                              ? "bg-amber-500"
                              : "bg-red-500",
                        )}
                      >
                        Q {Math.round(chunk.quality_score * 100)}%
                      </span>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-[hsl(var(--foreground))]">
                    {chunk.text_preview}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
