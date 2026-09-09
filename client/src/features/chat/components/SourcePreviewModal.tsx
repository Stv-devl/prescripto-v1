import { FileText, X } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import type { Source } from "../types/types";
import { cleanText } from "../utils/textCleaning";

interface SourcePreviewModalProps {
  source: Source;
  onClose: () => void;
}

export function SourcePreviewModal({
  source,
  onClose,
}: SourcePreviewModalProps) {
  const displayText = useMemo(
    () => (source.text ? cleanText(source.text) : ""),
    [source.text],
  );
  const { dialogRef } = useModalDialog<HTMLDivElement>({ isOpen: true });

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <div
        className="absolute inset-0 bg-black/60"
        role="presentation"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="relative w-full max-w-2xl rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label="Aperçu de la source"
        tabIndex={-1}
      >
        <header className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <FileText
              className="h-5 w-5 shrink-0 text-[hsl(var(--primary))]"
              aria-hidden="true"
            />
            <h2 className="text-lg font-semibold truncate">
              {source.filename}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="shrink-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="mb-4 flex flex-wrap gap-2">
          <Badge variant="outline">Page {source.page}</Badge>
          {source.lot && <Badge variant="outline">Lot : {source.lot}</Badge>}
          {source.phase && (
            <Badge variant="outline">Phase : {source.phase}</Badge>
          )}
        </div>

        {displayText ? (
          <div className="max-h-96 overflow-y-auto rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-4">
            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-[hsl(var(--muted-foreground))]">
              {displayText}
            </pre>
          </div>
        ) : (
          <p className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-4 text-center text-sm text-muted-foreground">
            Contenu non disponible pour cette source.
          </p>
        )}

        <footer className="mt-4 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
        </footer>
      </div>
    </div>
  );
}
