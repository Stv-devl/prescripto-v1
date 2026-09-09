import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { useBatchEnrichKeywords } from "../hooks/hooks";
import { useAdminStore } from "../stores/store";
import type { QualityAlerts } from "../types/types";

interface StatsOverviewQualityAlertsProps {
  qualityAlerts: QualityAlerts;
  projectId: string;
}

/** The quality-alert filter buttons and the per-lot keyword re-enrichment workflow. */
export function StatsOverviewQualityAlerts({ qualityAlerts, projectId }: StatsOverviewQualityAlertsProps) {
  const setFilters = useAdminStore((s) => s.setFilters);
  const setActiveTab = useAdminStore((s) => s.setActiveTab);
  const claimActionFailure = useAdminStore((s) => s.claimActionFailure);
  const releaseActionFailure = useAdminStore((s) => s.releaseActionFailure);
  const batchEnrich = useBatchEnrichKeywords(projectId);
  const [enrichResult, setEnrichResult] = useState<string | null>(null);

  /**
   * `useBatchEnrichKeywords` reports every failure to the store so it
   * outlives this tab. While it says it itself, claim it so the banner stays
   * quiet; the release on unmount hands it straight back rather than losing
   * it — the same pattern `ChunkDetail`/`DocumentChunkView` already use.
   */
  useEffect(() => {
    if (!batchEnrich.error) return;
    claimActionFailure();
    return releaseActionFailure;
  }, [batchEnrich.error, claimActionFailure, releaseActionFailure]);

  function handleAlertClick(filter: Record<string, string | number | boolean | undefined>): void {
    setFilters(filter);
    setActiveTab("table");
  }

  return (
    <section className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-400">
        <AlertTriangle className="h-4 w-4" />
        Alertes qualité
      </h3>
      <div className="flex flex-wrap gap-2">
        {qualityAlerts.chunks_without_keywords > 0 && (
          <button
            onClick={() => handleAlertClick({ has_keywords: false })}
            className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
          >
            Sans keywords : {qualityAlerts.chunks_without_keywords}
          </button>
        )}
        {qualityAlerts.chunks_heading_only > 0 && (
          <button
            onClick={() => handleAlertClick({ content_type: "heading" })}
            className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
          >
            Heading-only : {qualityAlerts.chunks_heading_only}
          </button>
        )}
        {qualityAlerts.chunks_very_short > 0 && (
          <button
            onClick={() => handleAlertClick({ max_chars: 100 })}
            className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
          >
            Très courts (&lt;100) : {qualityAlerts.chunks_very_short}
          </button>
        )}
        {qualityAlerts.chunks_oversized > 0 && (
          <button
            onClick={() => handleAlertClick({ min_chars: 2500 })}
            className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
          >
            Oversized (&gt;2500) : {qualityAlerts.chunks_oversized}
          </button>
        )}
        {qualityAlerts.documents_with_errors > 0 && (
          <span className="rounded-full bg-red-500/15 px-3 py-1 text-xs font-medium text-red-400">
            Documents en erreur : {qualityAlerts.documents_with_errors}
          </span>
        )}

        {/* Batch enrich button */}
        {qualityAlerts.chunks_without_keywords > 0 && (
          <button
            onClick={() => {
              setEnrichResult(null);
              batchEnrich.mutate(undefined, {
                onSuccess: (data) => {
                  setEnrichResult(`${data.updated_count} chunks enrichis avec des keywords.`);
                },
              });
            }}
            disabled={batchEnrich.isPending}
            className="flex items-center gap-1.5 rounded-full bg-[#FFC300]/15 px-3 py-1 text-xs font-medium text-[#FFC300] transition-colors hover:bg-[#FFC300]/25 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${batchEnrich.isPending ? "animate-spin" : ""}`} />
            {batchEnrich.isPending ? "En cours..." : "Re-enrichir les keywords"}
          </button>
        )}
      </div>

      {batchEnrich.error && (
        <ErrorMessage error={batchEnrich.error} />
      )}

      {enrichResult && (
        <p className="mt-2 text-xs text-emerald-400">
          {enrichResult}
          <button onClick={() => setEnrichResult(null)} className="ml-2 underline">
            Fermer
          </button>
        </p>
      )}
    </section>
  );
}
