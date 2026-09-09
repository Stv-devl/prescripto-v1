import { FileText } from "lucide-react";
import { useState } from "react";
import type { Source } from "../types/types";
import { SourcePreviewModal } from "./SourcePreviewModal";

interface ChatSourcesProps {
  sources: Source[];
}

export function ChatSources({ sources }: ChatSourcesProps) {
  const [selected, setSelected] = useState<Source | null>(null);

  if (sources.length === 0) return null;

  return (
    <>
      <aside className="mt-2 border-t border-[hsl(var(--border))] pt-2">
        <p className="mb-1 text-xs font-medium text-muted-foreground">
          Sources :
        </p>
        <ul className="flex flex-wrap gap-2">
          {sources.map((source, i) => (
            <li key={`${source.document_id}-${source.page}-${i}`}>
              <button
                type="button"
                onClick={() => setSelected(source)}
                className="inline-flex items-center gap-1 rounded bg-[hsl(var(--background))]/50 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-[hsl(var(--primary))]/10 hover:text-[hsl(var(--primary))]"
              >
                <FileText className="h-3 w-3" aria-hidden="true" />
                <span className="truncate max-w-[160px]">
                  {source.filename}
                </span>
                <span>p.{source.page}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      {selected && (
        <SourcePreviewModal
          source={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
