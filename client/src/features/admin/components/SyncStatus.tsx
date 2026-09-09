import { CheckCircle, XCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { cn } from "@/lib/utils";
import { useSyncCheck } from "../hooks/hooks";

interface SyncStatusProps {
  projectId: string;
}

interface MismatchFilterProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/**
 * The mismatch toggle, rendered whether or not the check succeeded: it resets
 * the page and rebuilds the query key, which is the only way back from a failed
 * page in a UI with no retry button.
 */
function MismatchFilter({ checked, onChange }: MismatchFilterProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-[hsl(var(--foreground))]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-[hsl(var(--border))] accent-[#FFC300]"
      />
      Afficher uniquement les désynchronisations
    </label>
  );
}

export function SyncStatus({ projectId }: SyncStatusProps) {
  const [page, setPage] = useState(1);
  const [onlyMismatches, setOnlyMismatches] = useState(false);
  const { data, isPending, error } = useSyncCheck(
    projectId,
    page,
    20,
    onlyMismatches,
  );

  if (isPending && !data) {
    return (
      <div className="space-y-3">
        <Skeleton variant="rectangular" className="h-16" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} variant="rectangular" className="h-11" />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        {error && <ErrorMessage error={error} />}
        <MismatchFilter
          checked={onlyMismatches}
          onChange={(checked) => {
            setOnlyMismatches(checked);
            setPage(1);
          }}
        />
        {page > 1 && (
          <button
            onClick={() => setPage(page - 1)}
            className="flex items-center gap-1.5 rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-sm text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))]"
          >
            <ChevronLeft className="h-4 w-4" />
            Page précédente
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <ErrorMessage error={error} />}

      {/* Summary banner */}
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg border p-4",
          data.synced
            ? "border-emerald-500/30 bg-emerald-500/10"
            : "border-red-500/30 bg-red-500/10",
        )}
      >
        {data.synced ? (
          <CheckCircle className="h-6 w-6 text-emerald-400" />
        ) : (
          <XCircle className="h-6 w-6 text-red-400" />
        )}
        <div>
          <p
            className={cn(
              "font-semibold",
              data.synced ? "text-emerald-400" : "text-red-400",
            )}
          >
            {data.synced ? "Synchronisé" : "Désynchronisation détectée"}
          </p>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            SQL : {data.total_sql.toLocaleString()} chunks — Qdrant :{" "}
            {data.total_qdrant.toLocaleString()} points
          </p>
        </div>
      </div>

      <MismatchFilter
        checked={onlyMismatches}
        onChange={(checked) => {
          setOnlyMismatches(checked);
          setPage(1);
        }}
      />

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))]">
        <table className="w-full text-sm">
          <thead className="border-b border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Document
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Chunks SQL
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Points Qdrant
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                Statut
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))]">
            {data.documents.items.map((doc) => (
              <tr
                key={doc.document_id}
                className={cn(
                  "bg-[hsl(var(--secondary))]/30",
                  doc.status === "mismatch" && "bg-red-500/5",
                )}
              >
                <td className="max-w-[250px] truncate px-4 py-2 font-medium text-[hsl(var(--foreground))]">
                  {doc.filename}
                </td>
                <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">{doc.sql_count}</td>
                <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">
                  {doc.qdrant_count}
                </td>
                <td className="px-4 py-2">
                  {doc.status === "synced" ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-400">
                      <CheckCircle className="h-3 w-3" /> Synced
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-medium text-red-400">
                      <XCircle className="h-3 w-3" /> Mismatch
                      {doc.missing_in_qdrant.length > 0 &&
                        ` (${doc.missing_in_qdrant.length} manquants)`}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data.documents.total > 20 && (
        <div className="flex items-center justify-between text-sm text-[hsl(var(--muted-foreground))]">
          <span>
            {data.documents.total} documents — Page {data.documents.page}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              aria-label="Page précédente"
              className="rounded-md border border-[hsl(var(--border))] p-1.5 transition-colors hover:bg-[hsl(var(--muted))] disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              disabled={data.documents.items.length < 20}
              onClick={() => setPage(page + 1)}
              aria-label="Page suivante"
              className="rounded-md border border-[hsl(var(--border))] p-1.5 transition-colors hover:bg-[hsl(var(--muted))] disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
