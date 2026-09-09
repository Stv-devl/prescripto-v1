import { Copy, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DocumentStats } from "../types/types";

interface DocumentChunkViewToolbarProps {
  documents: DocumentStats[];
  selectedDocumentId: string | null;
  onSelectDocument: (id: string | null) => void;
  onRechunkClick: () => void;
  isRechunkPending: boolean;
  showDuplicates: boolean;
  onToggleDuplicates: () => void;
}

/** Document selector plus its re-chunk and duplicates-toggle triggers, for `DocumentChunkView`. */
export function DocumentChunkViewToolbar({
  documents,
  selectedDocumentId,
  onSelectDocument,
  onRechunkClick,
  isRechunkPending,
  showDuplicates,
  onToggleDuplicates,
}: DocumentChunkViewToolbarProps): React.ReactElement {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select
        value={selectedDocumentId ?? ""}
        onChange={(e) => onSelectDocument(e.target.value || null)}
        className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
      >
        <option value="">Sélectionner un document...</option>
        {documents.map((doc) => (
          <option key={doc.document_id} value={doc.document_id}>
            {doc.filename} ({doc.chunk_count} chunks)
          </option>
        ))}
      </select>

      {selectedDocumentId && (
        <button
          onClick={onRechunkClick}
          disabled={isRechunkPending}
          className="flex items-center gap-1.5 rounded-md border border-[hsl(var(--border))] px-3 py-2 text-sm text-[hsl(var(--muted-foreground))] transition-colors hover:border-amber-500/50 hover:text-amber-400 disabled:opacity-50"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isRechunkPending && "animate-spin")} />
          Re-chunker
        </button>
      )}

      {selectedDocumentId && (
        <button
          onClick={onToggleDuplicates}
          className={cn(
            "flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors",
            showDuplicates
              ? "border-[#FFC300] bg-[#FFC300]/10 text-[#FFC300]"
              : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:border-[#FFC300]/50 hover:text-[hsl(var(--foreground))]",
          )}
        >
          <Copy className="h-3.5 w-3.5" />
          Doublons
        </button>
      )}
    </div>
  );
}
