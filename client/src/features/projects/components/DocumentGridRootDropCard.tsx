import { motion } from "framer-motion";
import { CornerLeftUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface DocumentGridRootDropCardProps {
  dragOverRoot: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onDragLeave: () => void;
}

/** The "move to root" drop-target card, shown only while browsing inside a folder. */
export function DocumentGridRootDropCard({
  dragOverRoot,
  onDragOver,
  onDrop,
  onDragLeave,
}: DocumentGridRootDropCardProps): React.ReactElement {
  return (
    <motion.article
      key="root-drop"
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "flex items-center gap-2 rounded-md border-2 border-dashed px-3 py-2 transition-colors",
        dragOverRoot
          ? "border-[#FFC300] bg-[#FFC300]/10"
          : "border-[hsl(var(--border))] hover:border-[hsl(var(--muted-foreground))]",
      )}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragLeave={onDragLeave}
    >
      <CornerLeftUp className="h-4 w-4 shrink-0 text-muted-foreground" />
      <p className="truncate text-xs text-muted-foreground">Racine</p>
    </motion.article>
  );
}
