import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { cn, formatSize, relativeTime } from "@/lib/utils";
import type { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import { STATUS_LABELS, STATUS_STYLES, getFileIcon, ProcessingProgress } from "../utils/documentDisplay";

interface DocumentListRowProps {
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

/** One document row of `DocumentList`'s table. */
export function DocumentListRow({
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
}: DocumentListRowProps): React.ReactElement {
  const { icon: FileIcon, colorClass } = getFileIcon(doc.filename);

  return (
    <motion.tr
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, x: -20 }}
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
        "border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted))] transition-colors",
        draggable && "cursor-grab active:cursor-grabbing",
        onDocumentClick && "cursor-pointer",
        dd.draggingDocId === doc.id && "opacity-40",
        isSelected && "bg-[#FFC300]/5",
      )}
    >
      {hasSelection && (
        <td className="w-10 py-3 pr-2">
          <Checkbox
            checked={isSelected}
            onChange={() => onToggleSelect?.(doc.id)}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Sélectionner ${doc.filename}`}
          />
        </td>
      )}
      <td className="py-3 pr-4 font-medium">
        <span className="inline-flex items-center gap-2 truncate max-w-[240px]">
          <FileIcon className={cn("h-4 w-4 shrink-0", colorClass)} />
          {doc.filename}
        </span>
      </td>
      <td className="py-3 pr-4 text-muted-foreground">{doc.type || "—"}</td>
      <td className="py-3 pr-4 text-muted-foreground">{doc.lot || "—"}</td>
      <td className="py-3 pr-4 text-muted-foreground">{doc.phase || "—"}</td>
      <td className="py-3 pr-4 text-muted-foreground">{formatSize(doc.size)}</td>
      <td className="py-3 pr-4">
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
      </td>
      <td
        className="py-3 pr-4 text-muted-foreground text-xs"
        title={new Date(doc.created_at).toLocaleString("fr-FR")}
      >
        {relativeTime(doc.created_at)}
      </td>
      <td className="py-3">
        <span
          className="flex items-center justify-end gap-1"
          role="presentation"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="icon"
            className="group h-8 w-8 hover:scale-110 transition-all"
            onClick={() => onDelete(doc)}
            disabled={isDeleting}
            aria-label={`Supprimer ${doc.filename}`}
          >
            <Trash2 className="h-4 w-4 text-muted-foreground group-hover:!text-red-500 transition-colors" />
          </Button>
        </span>
      </td>
    </motion.tr>
  );
}
