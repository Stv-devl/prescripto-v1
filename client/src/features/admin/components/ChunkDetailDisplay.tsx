import { cn } from "@/lib/utils";
import type { ChunkDetail } from "../types/types";
import { CONTENT_TYPE_BADGES } from "./chunkContentTypeBadges";

interface ChunkDetailDisplayProps {
  chunk: ChunkDetail;
}

export function ChunkDetailDisplay({ chunk }: ChunkDetailDisplayProps) {
  return (
    <>
      {chunk.quality_score != null && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[hsl(var(--muted-foreground))]">Qualité</span>
          <div className="h-2 flex-1 rounded-full bg-[hsl(var(--muted))]">
            <div
              className={cn(
                "h-full rounded-full",
                chunk.quality_score >= 0.7
                  ? "bg-emerald-500"
                  : chunk.quality_score >= 0.4
                    ? "bg-amber-500"
                    : "bg-red-500",
              )}
              style={{ width: `${Math.round(chunk.quality_score * 100)}%` }}
            />
          </div>
          <span className="min-w-[2.5rem] text-right text-xs font-medium text-[hsl(var(--foreground))]">
            {Math.round(chunk.quality_score * 100)}%
          </span>
        </div>
      )}

      <section className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-4">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Document
          </dt>
          <dd className="truncate font-medium text-[hsl(var(--foreground))]">{chunk.filename}</dd>

          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Page / Position
          </dt>
          <dd className="font-medium text-[hsl(var(--foreground))]">
            p.{chunk.page} / pos.{chunk.position}
          </dd>

          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Lot
          </dt>
          <dd className="font-medium text-[hsl(var(--foreground))]">{chunk.lot || "—"}</dd>

          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Type doc
          </dt>
          <dd className="font-medium text-[hsl(var(--foreground))]">{chunk.type}</dd>

          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Taille
          </dt>
          <dd className="font-medium text-[hsl(var(--foreground))]">
            {chunk.char_count?.toLocaleString() ?? "—"} chars
          </dd>

          <dt className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Content type
          </dt>
          <dd>
            {chunk.content_type && (
              <span
                className={cn(
                  "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                  CONTENT_TYPE_BADGES[chunk.content_type] ?? "bg-slate-500/15 text-slate-400",
                )}
              >
                {chunk.content_type}
              </span>
            )}
          </dd>
        </dl>
      </section>

      {chunk.section_title && (
        <section>
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Section
          </h3>
          <p className="text-sm text-[hsl(var(--foreground))]">{chunk.section_title}</p>
        </section>
      )}

      {chunk.parent_sections && chunk.parent_sections.length > 0 && (
        <section>
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Hiérarchie
          </h3>
          <div className="space-y-0.5">
            {chunk.parent_sections.map((s, i) => (
              <p
                key={i}
                className="text-sm text-[hsl(var(--muted-foreground))]"
                style={{ paddingLeft: `${i * 12}px` }}
              >
                {s}
              </p>
            ))}
          </div>
        </section>
      )}

      {chunk.keywords && chunk.keywords.length > 0 && (
        <section>
          <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
            Keywords
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {chunk.keywords.map((kw) => (
              <span
                key={kw}
                className="rounded-full bg-[#FFC300]/15 px-2.5 py-0.5 text-xs font-medium text-[#FFC300]"
              >
                {kw}
              </span>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
