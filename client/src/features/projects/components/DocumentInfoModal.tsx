import { X } from "lucide-react";
import { useEffect } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import { formatSize, relativeTime , cn } from "@/lib/utils";
import type { Document } from "../types/types";
import { STATUS_STYLES, STATUS_LABELS, getFileIcon } from "./DocumentList";

interface DocumentInfoModalProps {
  document: Document;
  onClose: () => void;
}

/**
 * Centered modal displaying document metadata.
 * Triggered via context menu "Infos".
 */
export function DocumentInfoModal({
  document: doc,
  onClose,
}: DocumentInfoModalProps): React.ReactElement {
  const { icon: FileIcon, colorClass } = getFileIcon(doc.filename);
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
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        className="absolute inset-0 bg-black/60"
        role="presentation"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="relative w-full max-w-lg rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label="Informations du document"
        tabIndex={-1}
      >
        {/* Header */}
        <header className="mb-5 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <FileIcon className={cn("h-10 w-10 shrink-0", colorClass)} />
            <h2
              className="text-base font-semibold text-[hsl(var(--foreground))] break-words"
              title={doc.filename}
            >
              {doc.filename}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </header>

        {/* Metadata */}
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
          <dt className="text-muted-foreground">Type</dt>
          <dd className="text-[hsl(var(--foreground))]">
            {doc.type || "Non classé"}
          </dd>

          <dt className="text-muted-foreground">Lot</dt>
          <dd className="text-[hsl(var(--foreground))]">{doc.lot || "—"}</dd>

          <dt className="text-muted-foreground">Phase</dt>
          <dd className="text-[hsl(var(--foreground))]">{doc.phase || "—"}</dd>

          <dt className="text-muted-foreground">Taille</dt>
          <dd className="text-[hsl(var(--foreground))]">
            {formatSize(doc.size)}
          </dd>

          <dt className="text-muted-foreground">Statut</dt>
          <dd>
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                STATUS_STYLES[doc.status] ?? STATUS_STYLES.error,
              )}
            >
              {STATUS_LABELS[doc.status] ?? doc.status}
            </Badge>
          </dd>

          <dt className="text-muted-foreground">Créé le</dt>
          <dd className="text-[hsl(var(--foreground))]">
            <time title={new Date(doc.created_at).toLocaleString("fr-FR")}>
              {new Date(doc.created_at).toLocaleDateString("fr-FR", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </time>
            <span className="ml-1.5 text-xs text-muted-foreground">
              ({relativeTime(doc.created_at)})
            </span>
          </dd>
        </dl>

        {/* Footer */}
        <footer className="mt-5 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
        </footer>
      </div>
    </div>
  );
}
