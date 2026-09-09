import { AlertTriangle, Database, FileText, Ruler, Shield } from "lucide-react";
import type { ChunkStatsResponse } from "../types/types";

interface StatsOverviewKpiCardsProps {
  stats: ChunkStatsResponse;
  totalAlerts: number;
}

/** The five KPI cards (chunks, documents, average size, quality score, alert count) atop the admin stats tab. */
export function StatsOverviewKpiCards({ stats, totalAlerts }: StatsOverviewKpiCardsProps) {
  const avgCharCount =
    stats.total_chunks > 0
      ? Math.round(
          stats.by_document.reduce((sum, d) => sum + d.avg_char_count * d.chunk_count, 0) /
            stats.total_chunks,
        )
      : 0;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FFC300]/15">
            <Database className="h-5 w-5 text-[#FFC300]" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Total chunks
            </p>
            <p className="text-2xl font-bold text-[hsl(var(--foreground))]">
              {stats.total_chunks.toLocaleString()}
            </p>
          </div>
        </div>
      </article>

      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15">
            <FileText className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Documents indexés
            </p>
            <p className="text-2xl font-bold text-[hsl(var(--foreground))]">
              {stats.total_documents}
            </p>
          </div>
        </div>
      </article>

      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FFC300]/15">
            <Ruler className="h-5 w-5 text-[#FFC300]" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Taille moyenne
            </p>
            <p className="text-2xl font-bold text-[hsl(var(--foreground))]">
              {avgCharCount.toLocaleString()}
              <span className="ml-1 text-sm font-normal text-[hsl(var(--muted-foreground))]">
                chars
              </span>
            </p>
          </div>
        </div>
      </article>

      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15">
            <Shield className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Score qualité
            </p>
            <p className="text-2xl font-bold text-[hsl(var(--foreground))]">
              {Math.round((stats.avg_quality_score ?? 0) * 100)}
              <span className="ml-1 text-sm font-normal text-[hsl(var(--muted-foreground))]">
                %
              </span>
            </p>
          </div>
        </div>
      </article>

      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
              Alertes qualité
            </p>
            <p className="text-2xl font-bold text-[hsl(var(--foreground))]">{totalAlerts}</p>
          </div>
        </div>
      </article>
    </div>
  );
}
