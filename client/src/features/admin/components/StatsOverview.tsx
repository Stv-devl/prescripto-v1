import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import type { ChunkStatsResponse } from "../types/types";
import { ContentTypeChart } from "./ContentTypeChart";
import { LotBreakdown } from "./LotBreakdown";
import { SizeDistribution } from "./SizeDistribution";
import { StatsOverviewKpiCards } from "./StatsOverviewKpiCards";
import { StatsOverviewQualityAlerts } from "./StatsOverviewQualityAlerts";

interface StatsOverviewProps {
  stats: ChunkStatsResponse | undefined;
  isPending: boolean;
  projectId: string;
  error: Error | null;
}

export function StatsOverview({ stats, isPending, projectId, error }: StatsOverviewProps) {
  if (isPending) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" className="h-24" />
        ))}
      </div>
    );
  }

  if (error && !stats) {
    return <ErrorMessage error={error} />;
  }

  if (!stats) return null;

  const totalAlerts =
    stats.quality_alerts.chunks_without_keywords +
    stats.quality_alerts.chunks_heading_only +
    stats.quality_alerts.chunks_very_short +
    stats.quality_alerts.chunks_oversized +
    stats.quality_alerts.documents_with_errors;

  return (
    <div className="space-y-6">
      {error && <ErrorMessage error={error} />}

      <StatsOverviewKpiCards stats={stats} totalAlerts={totalAlerts} />

      {totalAlerts > 0 && (
        <StatsOverviewQualityAlerts qualityAlerts={stats.quality_alerts} projectId={projectId} />
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <SizeDistribution data={stats.size_distribution} />
        <ContentTypeChart data={stats.by_content_type} />
        <LotBreakdown data={stats.by_lot} />
      </div>
    </div>
  );
}
