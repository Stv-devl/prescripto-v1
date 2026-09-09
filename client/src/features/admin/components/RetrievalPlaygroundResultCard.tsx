import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PlaygroundSearchResult } from "../types/types";
import { CONTENT_TYPE_BADGES } from "./chunkContentTypeBadges";

function qualityColor(score: number): string {
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.4) return "bg-amber-500";
  return "bg-red-500";
}

function scoreBarColor(score: number): string {
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.5) return "bg-[#FFC300]";
  if (score >= 0.3) return "bg-orange-500";
  return "bg-red-500";
}

interface RetrievalPlaygroundResultCardProps {
  result: PlaygroundSearchResult;
  rank: number;
  isExpanded: boolean;
  onToggle: () => void;
  onNavigate: () => void;
}

/** One search result row in the retrieval playground, with its expand/collapse and navigation actions. */
export function RetrievalPlaygroundResultCard({
  result,
  rank,
  isExpanded,
  onToggle,
  onNavigate,
}: RetrievalPlaygroundResultCardProps) {
  const scorePercent = Math.round(result.score * 100);
  const qualityPercent = Math.round(result.quality_score * 100);

  return (
    <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/30 transition-colors hover:bg-[hsl(var(--secondary))]/50">
      <div className="p-4">
        {/* Header row */}
        <div className="mb-3 flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#FFC300]/15 text-xs font-bold text-[#FFC300]">
            {rank}
          </span>

          {/* Score bar */}
          <div className="flex flex-1 items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-[hsl(var(--muted))]">
              <div
                className={cn("h-full rounded-full transition-all", scoreBarColor(result.score))}
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="min-w-[3.5rem] text-right text-xs font-medium text-[hsl(var(--foreground))]">
              {scorePercent}% sim
            </span>
          </div>

          {/* Quality badge */}
          <span
            className={cn(
              "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white",
              qualityColor(result.quality_score),
            )}
          >
            Q {qualityPercent}%
          </span>
        </div>

        {/* Metadata */}
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
          <span className="font-medium text-[hsl(var(--foreground))]">{result.filename}</span>
          <span>p.{result.page}</span>
          <span>pos.{result.position}</span>
          {result.lot && <span className="rounded bg-[hsl(var(--muted))] px-1.5 py-0.5">{result.lot}</span>}
          {result.content_type && (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 font-medium",
                CONTENT_TYPE_BADGES[result.content_type] ?? "bg-slate-500/15 text-slate-400",
              )}
            >
              {result.content_type}
            </span>
          )}
          <span>{result.char_count} chars</span>
        </div>

        {/* Keywords */}
        {result.keywords.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1">
            {result.keywords.map((kw) => (
              <span
                key={kw}
                className="rounded bg-[#FFC300]/10 px-1.5 py-0.5 text-xs text-[#FFC300]"
              >
                {kw}
              </span>
            ))}
          </div>
        )}

        {/* Text preview */}
        <p className="text-sm leading-relaxed text-[hsl(var(--foreground))]">
          {result.text_preview}
        </p>

        {/* Expanded text */}
        {isExpanded && (
          <pre className="mt-3 max-h-[300px] overflow-auto rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 text-xs leading-relaxed text-[hsl(var(--foreground))] whitespace-pre-wrap">
            {result.text}
          </pre>
        )}

        {/* Actions */}
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={onToggle}
            className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))] transition-colors hover:text-[#FFC300]"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="h-3 w-3" /> Réduire
              </>
            ) : (
              <>
                <ChevronDown className="h-3 w-3" /> Voir le texte complet
              </>
            )}
          </button>
          <button
            onClick={onNavigate}
            className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))] transition-colors hover:text-[#FFC300]"
          >
            Voir le détail
          </button>
        </div>
      </div>
    </article>
  );
}
