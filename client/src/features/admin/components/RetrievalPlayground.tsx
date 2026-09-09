import { Clock, Search } from "lucide-react";
import { useState } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { usePlaygroundSearch } from "../hooks/hooks";
import { useAdminStore } from "../stores/store";
import type { ChunkStatsResponse } from "../types/types";
import { RetrievalPlaygroundResultCard } from "./RetrievalPlaygroundResultCard";
import { RetrievalPlaygroundSearchForm } from "./RetrievalPlaygroundSearchForm";

interface RetrievalPlaygroundProps {
  projectId: string;
  stats: ChunkStatsResponse | undefined;
}

export function RetrievalPlayground({ projectId, stats }: RetrievalPlaygroundProps) {
  const [query, setQuery] = useState("");
  const [lot, setLot] = useState("");
  const [contentType, setContentType] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { selectChunk, setActiveTab } = useAdminStore();

  const { mutate, data, isPending, error } = usePlaygroundSearch(projectId);

  function handleSearch(): void {
    if (!query.trim()) return;
    mutate({
      query: query.trim(),
      lot: lot || undefined,
      content_type: contentType || undefined,
      limit: 20,
    });
  }

  function handleNavigateToChunk(chunkId: string): void {
    selectChunk(chunkId);
    setActiveTab("table");
  }

  const lots = stats ? Object.keys(stats.by_lot).sort() : [];
  const contentTypes = stats ? Object.keys(stats.by_content_type).sort() : [];

  return (
    <div className="space-y-6">
      <RetrievalPlaygroundSearchForm
        query={query}
        onQueryChange={setQuery}
        lot={lot}
        onLotChange={setLot}
        contentType={contentType}
        onContentTypeChange={setContentType}
        lots={lots}
        contentTypes={contentTypes}
        isPending={isPending}
        onSearch={handleSearch}
      />

      {/* Results */}
      {data && (
        <section className="space-y-4">
          {/* Metadata bar */}
          <div className="flex items-center gap-4 text-sm text-[hsl(var(--muted-foreground))]">
            <span className="flex items-center gap-1.5">
              <Search className="h-3.5 w-3.5" />
              {data.total_results} résultats
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              {data.query_time_ms} ms
            </span>
          </div>

          {data.results.length === 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-400">
              Aucun chunk trouvé pour cette requête. Cela peut indiquer un problème de couverture du RAG.
            </div>
          )}

          {/* Result cards */}
          <div className="space-y-3">
            {data.results.map((result, index) => (
              <RetrievalPlaygroundResultCard
                key={result.chunk_id}
                result={result}
                rank={index + 1}
                isExpanded={expandedId === result.chunk_id}
                onToggle={() =>
                  setExpandedId(expandedId === result.chunk_id ? null : result.chunk_id)
                }
                onNavigate={() => handleNavigateToChunk(result.chunk_id)}
              />
            ))}
          </div>
        </section>
      )}

      {error && <ErrorMessage error={error} />}

      {isPending && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} variant="rectangular" className="h-24" />
          ))}
        </div>
      )}
    </div>
  );
}
