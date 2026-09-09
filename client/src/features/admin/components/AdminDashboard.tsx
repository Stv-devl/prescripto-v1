import { BarChart3, Database, FileText, RefreshCw, Search, X } from "lucide-react";
import { useRef } from "react";
import { createPortal } from "react-dom";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { useRovingTabs } from "@/hooks/useRovingTabs";
import { toServiceError } from "@/lib/result";
import { cn } from "@/lib/utils";
import { useChunks, useChunkStats, useDocumentChunks } from "../hooks/hooks";
import { useAdminStore, type AdminActionKind, type AdminTab } from "../stores/store";
import { ChunkDetail } from "./ChunkDetail";
import { ChunkFilters } from "./ChunkFilters";
import { ChunkTable } from "./ChunkTable";
import { DocumentChunkView } from "./DocumentChunkView";
import { RetrievalPlayground } from "./RetrievalPlayground";
import { StatsOverview } from "./StatsOverview";
import { SyncStatus } from "./SyncStatus";

const TABS = [
  { key: "dashboard", label: "Dashboard", icon: BarChart3 },
  { key: "table", label: "Table", icon: Database },
  { key: "document", label: "Document", icon: FileText },
  { key: "playground", label: "Playground", icon: Search },
  { key: "sync", label: "Sync", icon: RefreshCw },
] as const;

const TAB_KEYS: readonly AdminTab[] = TABS.map((tab) => tab.key);

/** The French label the banner names the failed action with, never the error text itself. */
const ACTION_LABELS: Record<AdminActionKind, string> = {
  update: "Échec de la modification du chunk",
  split: "Échec de la scission du chunk",
  merge: "Échec de la fusion des chunks",
  delete: "Échec de la suppression du chunk",
  rechunk: "Échec du re-chunking du document",
  enrich: "Échec de l'enrichissement des keywords",
};

/**
 * Tabs whose content derives from the stats query without carrying its failure
 * themselves. The Dashboard tab is absent because `StatsOverview` says it, and
 * Sync is absent because nothing it renders comes from the stats.
 */
const STATS_DEPENDENT_TABS: ReadonlySet<AdminTab> = new Set<AdminTab>([
  "table",
  "document",
  "playground",
]);

/**
 * Two failures of the same cause render the same French sentence, and stacking
 * it twice tells the reader nothing. Deduplicate on the code, never on the tab:
 * hiding a stats failure because *some* other query failed left the filter
 * dropdowns empty and silent.
 */
function saysTheSameThing(a: Error | null, b: Error | null): boolean {
  if (!a || !b) return false;
  return toServiceError(a).code === toServiceError(b).code;
}

interface AdminDashboardProps {
  projectId: string;
}

export function AdminDashboard({ projectId }: AdminDashboardProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const activeTab = useAdminStore((s) => s.activeTab);
  const setActiveTab = useAdminStore((s) => s.setActiveTab);
  const filters = useAdminStore((s) => s.filters);
  const selectedChunkId = useAdminStore((s) => s.selectedChunkId);
  const selectedDocumentId = useAdminStore((s) => s.selectedDocumentId);
  const actionFailure = useAdminStore((s) => s.actionFailure);
  const actionFailureClaimants = useAdminStore((s) => s.actionFailureClaimants);
  const clearActionFailure = useAdminStore((s) => s.clearActionFailure);

  const reportedFailure =
    actionFailure &&
    actionFailureClaimants === 0 &&
    actionFailure.projectId === projectId
      ? actionFailure
      : null;

  const {
    data: stats,
    isPending: statsPending,
    error: statsError,
  } = useChunkStats(projectId);
  const {
    data: chunks,
    isPending: chunksPending,
    error: chunksError,
  } = useChunks(projectId, filters);
  const { error: documentChunksError } = useDocumentChunks(
    projectId,
    activeTab === "document" ? selectedDocumentId : null,
  );

  const tabError =
    activeTab === "table"
      ? chunksError
      : activeTab === "document"
        ? documentChunksError
        : null;

  /**
   * The stats failure, unless it says the same thing the action-failure
   * banner already does — the banner is not tab-scoped, so without this a
   * shared code duplicates on every tab that shows both, `dashboard` (via
   * `StatsOverview`'s own `error` prop) included.
   */
  const visibleStatsError = saysTheSameThing(statsError, reportedFailure?.error ?? null)
    ? null
    : statsError;

  const { setRef, onKeyDown, tabIndexFor } = useRovingTabs<AdminTab>(
    TAB_KEYS,
    activeTab,
    setActiveTab,
  );

  return (
    <div
      ref={contentRef}
      tabIndex={-1}
      className="space-y-6 outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#FFC300]"
    >
      {/* Tabs */}
      <div
        className="flex gap-1 border-b border-[hsl(var(--border))]"
        role="tablist"
      >
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              ref={setRef(tab.key)}
              role="tab"
              id={`admin-tab-${tab.key}`}
              aria-controls={`admin-tabpanel-${tab.key}`}
              aria-selected={active}
              tabIndex={tabIndexFor(tab.key)}
              onClick={() => setActiveTab(tab.key)}
              onKeyDown={(event) => onKeyDown(event, tab.key)}
              className={cn(
                "flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "border-[#FFC300] text-[#FFC300]"
                  : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]",
              )}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {reportedFailure &&
        createPortal(
          <div className="fixed inset-x-4 top-4 z-[45] mx-auto flex max-w-3xl items-start gap-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 shadow-lg sm:right-[540px]">
            <div className="flex-1">
              <p className="mb-1 text-sm font-medium text-[hsl(var(--foreground))]">
                {ACTION_LABELS[reportedFailure.kind]}
              </p>
              <ErrorMessage error={reportedFailure.error} />
            </div>
            <button
              type="button"
              onClick={clearActionFailure}
              aria-label="Masquer cette erreur"
              className="rounded-md p-2 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>,
          document.body,
        )}

      {STATS_DEPENDENT_TABS.has(activeTab) &&
        visibleStatsError &&
        !saysTheSameThing(visibleStatsError, tabError) && (
          <ErrorMessage error={visibleStatsError} />
        )}

      <div
        role="tabpanel"
        id={`admin-tabpanel-${activeTab}`}
        aria-labelledby={`admin-tab-${activeTab}`}
        tabIndex={0}
      >
        {activeTab === "dashboard" && (
          <StatsOverview
            stats={stats}
            isPending={statsPending}
            projectId={projectId}
            error={visibleStatsError}
          />
        )}

        {activeTab === "table" && (
          <div className="space-y-4">
            <ChunkFilters stats={stats} projectId={projectId} />
            <ChunkTable
              data={chunks}
              isPending={chunksPending}
              error={chunksError}
            />
          </div>
        )}

        {activeTab === "document" && (
          <DocumentChunkView projectId={projectId} stats={stats} />
        )}

        {activeTab === "playground" && (
          <RetrievalPlayground projectId={projectId} stats={stats} />
        )}

        {activeTab === "sync" && <SyncStatus projectId={projectId} />}
      </div>

      {/* Chunk detail side panel */}
      {selectedChunkId && (
        <ChunkDetail
          key={selectedChunkId}
          projectId={projectId}
          fallbackFocusRef={contentRef}
        />
      )}
    </div>
  );
}
