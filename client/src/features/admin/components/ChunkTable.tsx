import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, AlertTriangle } from "lucide-react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { cn } from "@/lib/utils";
import { useAdminStore } from "../stores/store";
import type { PaginatedChunks } from "../types/types";

const CONTENT_TYPE_BADGES: Record<string, string> = {
  specification: "bg-blue-500/15 text-blue-400",
  description: "bg-emerald-500/15 text-emerald-400",
  mixed: "bg-[#FFC300]/15 text-[#FFC300]",
  heading: "bg-slate-500/15 text-slate-400",
  quantity: "bg-green-500/15 text-green-400",
  admin: "bg-orange-500/15 text-orange-400",
};

interface ChunkTableProps {
  data: PaginatedChunks | undefined;
  isPending: boolean;
  error: Error | null;
}

type SortableColumn = "position" | "page" | "char_count" | "created_at";

export function ChunkTable({ data, isPending, error }: ChunkTableProps) {
  const { filters, setFilter, selectChunk } = useAdminStore();

  function handleSort(col: SortableColumn): void {
    if (filters.sort_by === col) {
      setFilter("sort_order", filters.sort_order === "asc" ? "desc" : "asc");
    } else {
      setFilter("sort_by", col);
    }
  }

  function SortIcon({ col }: { col: SortableColumn }) {
    if (filters.sort_by !== col) return null;
    return filters.sort_order === "asc" ? (
      <ChevronUp className="inline h-3 w-3" />
    ) : (
      <ChevronDown className="inline h-3 w-3" />
    );
  }

  if (isPending && !data) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" className="h-11" />
        ))}
      </div>
    );
  }

  if (error && !data) {
    return <ErrorMessage error={error} />;
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="space-y-4">
        {error && <ErrorMessage error={error} />}
        {!error && (
          <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-8 text-center text-sm text-[hsl(var(--muted-foreground))]">
            Aucun chunk trouvé avec ces filtres.
          </div>
        )}
      </div>
    );
  }

  const thClass =
    "px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]";
  const sortButtonClass =
    "flex w-full items-center gap-1 px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))] hover:text-[#FFC300]";

  function ariaSortFor(col: SortableColumn): "ascending" | "descending" | "none" {
    if (filters.sort_by !== col) return "none";
    return filters.sort_order === "asc" ? "ascending" : "descending";
  }

  return (
    <div className="space-y-4">
      {error && <ErrorMessage error={error} />}

      <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))]">
        <table className="w-full text-sm">
          <thead className="border-b border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50">
            <tr>
              <th className={thClass}>Document</th>
              <th aria-sort={ariaSortFor("position")}>
                <button
                  type="button"
                  onClick={() => handleSort("position")}
                  className={sortButtonClass}
                >
                  Pos <SortIcon col="position" />
                </button>
              </th>
              <th aria-sort={ariaSortFor("page")}>
                <button
                  type="button"
                  onClick={() => handleSort("page")}
                  className={sortButtonClass}
                >
                  Page <SortIcon col="page" />
                </button>
              </th>
              <th className={thClass}>Type</th>
              <th className={thClass}>Lot</th>
              <th aria-sort={ariaSortFor("char_count")}>
                <button
                  type="button"
                  onClick={() => handleSort("char_count")}
                  className={sortButtonClass}
                >
                  Chars <SortIcon col="char_count" />
                </button>
              </th>
              <th className={thClass}>Content</th>
              <th className={thClass}>Keywords</th>
              <th className={thClass}>Qualité</th>
              <th className={thClass}>Aperçu</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))]">
            {data.items.map((chunk) => {
              const isSmall = chunk.char_count !== null && chunk.char_count < 100;
              const isLarge = chunk.char_count !== null && chunk.char_count >= 2500;
              return (
                <tr
                  key={chunk.id}
                  onClick={() => selectChunk(chunk.id)}
                  className="cursor-pointer bg-[hsl(var(--secondary))]/30 transition-colors hover:bg-[hsl(var(--muted))]"
                >
                  <td className="max-w-[140px] truncate px-3 py-2 font-medium text-[hsl(var(--foreground))]">
                    {chunk.filename}
                  </td>
                  <td className="px-3 py-2 text-[hsl(var(--muted-foreground))]">{chunk.position}</td>
                  <td className="px-3 py-2 text-[hsl(var(--muted-foreground))]">{chunk.page}</td>
                  <td className="px-3 py-2 text-[hsl(var(--muted-foreground))]">{chunk.type}</td>
                  <td className="max-w-[110px] truncate px-3 py-2 text-[hsl(var(--muted-foreground))]">
                    {chunk.lot || "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "flex items-center gap-1",
                        (isSmall || isLarge) ? "text-amber-400" : "text-[hsl(var(--muted-foreground))]",
                      )}
                    >
                      {(isSmall || isLarge) && <AlertTriangle className="h-3 w-3" />}
                      {chunk.char_count ?? "—"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
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
                  </td>
                  <td className="max-w-[140px] px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {chunk.keywords?.slice(0, 3).map((kw) => (
                        <span
                          key={kw}
                          className="rounded bg-[hsl(var(--muted))] px-1.5 py-0.5 text-xs text-[hsl(var(--muted-foreground))]"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {chunk.quality_score != null && (
                      <div className="flex items-center gap-1.5">
                        <div className="h-1.5 w-12 rounded-full bg-[hsl(var(--muted))]">
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
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">
                          {Math.round(chunk.quality_score * 100)}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="max-w-[180px] truncate px-3 py-2 text-xs text-[hsl(var(--muted-foreground))]">
                    {chunk.text_preview}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-[hsl(var(--muted-foreground))]">
        <span>
          {data.total.toLocaleString()} chunks — Page {data.page}/{data.total_pages}
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled={data.page <= 1}
            onClick={() => setFilter("page", data.page - 1)}
            aria-label="Page précédente"
            className="rounded-md border border-[hsl(var(--border))] p-1.5 transition-colors hover:bg-[hsl(var(--muted))] disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            disabled={data.page >= data.total_pages}
            onClick={() => setFilter("page", data.page + 1)}
            aria-label="Page suivante"
            className="rounded-md border border-[hsl(var(--border))] p-1.5 transition-colors hover:bg-[hsl(var(--muted))] disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
