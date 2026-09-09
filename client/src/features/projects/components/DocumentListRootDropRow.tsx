import { CornerLeftUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentListRootDropRowProps {
  hasSelection: boolean;
  dragOverRoot: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onDragLeave: () => void;
}

/** The "move to root" drop-target row, shown only while browsing inside a folder. */
export function DocumentListRootDropRow({
  hasSelection,
  dragOverRoot,
  onDragOver,
  onDrop,
  onDragLeave,
}: DocumentListRootDropRowProps): React.ReactElement {
  return (
    <tr
      className={cn(
        "border-b border-[hsl(var(--border))] transition-colors",
        dragOverRoot ? "border-[#FFC300] bg-[#FFC300]/10" : "hover:bg-[hsl(var(--muted))]",
      )}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragLeave={onDragLeave}
    >
      <td className="py-3 pr-4 font-medium" colSpan={hasSelection ? 10 : 9}>
        <span className="inline-flex items-center gap-2 text-muted-foreground">
          <CornerLeftUp className="h-4 w-4 shrink-0" />
          Déplacer vers la racine
        </span>
      </td>
    </tr>
  );
}
