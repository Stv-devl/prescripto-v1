import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { cn, formatSize, relativeTime } from "@/lib/utils";
import type { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import { STATUS_LABELS, STATUS_STYLES, getFileIcon, ProcessingProgress } from "../utils/documentDisplay";

interface DocumentGridDocumentCardProps {
  doc: Document;
  isSelected: boolean;
  hasSelection: boolean;
  onToggleSelect?: (id: string) => void;
  onDocumentClick?: (doc: Document) => void;
  onContextMenu?: (
    e: React.MouseEvent,
    target: { type: "document"; item: Document } | { type: "folder"; item: Folder },
  ) => void;
  onDelete: (doc: Document) => void;
  isDeleting: boolean;
  draggable: boolean;
  dd: Pick<
    ReturnType<typeof useFolderDragDrop>,
    "draggingDocId" | "handleDragStart" | "handleDragEnd"
  >;
}

/** One document card of `DocumentGrid`. */
export function DocumentGridDocumentCard({
  doc,
  isSelected,
  hasSelection,
  onToggleSelect,
  onDocumentClick,
  onContextMenu,
  onDelete,
  isDeleting,
  draggable,
  dd,
}: DocumentGridDocumentCardProps): React.ReactElement {
  const { icon: FileIcon, colorClass } = getFileIcon(doc.filename);

  return (
    <motion.article
      key={doc.id}
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      draggable={draggable}
      onDragStart={(e) => dd.handleDragStart(e as unknown as React.DragEvent, doc)}
      onDragEnd={dd.handleDragEnd}
      onClick={() => onDocumentClick?.(doc)}
      onContextMenu={(e) => {
        if (onContextMenu) {
          e.preventDefault();
          onContextMenu(e as unknown as React.MouseEvent, {
            type: "document",
            item: doc,
          });
        }
      }}
      className={cn(
        "group/card relative flex flex-col gap-3 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-4 hover:bg-[hsl(var(--muted))] transition-colors",
        draggable && "cursor-grab active:cursor-grabbing",
        onDocumentClick && "cursor-pointer",
        dd.draggingDocId === doc.id && "opacity-40",
        isSelected && "border-[#FFC300]/40 bg-[#FFC300]/5",
      )}
    >
      {/* Checkbox overlay */}
      {hasSelection && (
        <div
          className={cn(
            "absolute left-2 top-2 z-10 transition-opacity",
            isSelected ? "opacity-100" : "opacity-0 group-hover/card:opacity-100",
          )}
          role="presentation"
          onClick={(e) => e.stopPropagation()}
        >
          <Checkbox
            checked={isSelected}
            onChange={() => onToggleSelect?.(doc.id)}
            aria-label={`Sélectionner ${doc.filename}`}
          />
        </div>
      )}

      <header className="flex items-start gap-3">
        <FileIcon className={cn("h-8 w-8 shrink-0", colorClass)} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" title={doc.filename}>
            {doc.filename}
          </p>
          <p className="text-xs text-muted-foreground">
            {doc.type || "Non classé"} {doc.lot ? `· ${doc.lot}` : ""}{" "}
            {doc.phase ? `· ${doc.phase}` : ""}
          </p>
        </div>
      </header>

      <div className="flex items-center justify-between">
        {doc.status === "processing" || doc.status === "uploading" ? (
          <ProcessingProgress startedAt={doc.created_at} />
        ) : (
          <Badge
            variant="outline"
            className={cn("text-xs", STATUS_STYLES[doc.status] ?? STATUS_STYLES.error)}
          >
            {STATUS_LABELS[doc.status] ?? doc.status}
          </Badge>
        )}
      </div>

      <footer className="flex items-center justify-between border-t border-[hsl(var(--border))] pt-3 text-xs text-muted-foreground">
        <span>
          {formatSize(doc.size)} ·{" "}
          <time title={new Date(doc.created_at).toLocaleString("fr-FR")}>
            {relativeTime(doc.created_at)}
          </time>
        </span>
        <span
          className="inline-flex items-center gap-1"
          role="presentation"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="icon"
            className="group h-7 w-7 hover:scale-110 transition-all"
            onClick={() => onDelete(doc)}
            disabled={isDeleting}
            aria-label={`Supprimer ${doc.filename}`}
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground group-hover:!text-red-500 transition-colors" />
          </Button>
        </span>
      </footer>
    </motion.article>
  );
}
