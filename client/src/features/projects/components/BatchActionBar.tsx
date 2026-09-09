import { motion, AnimatePresence } from "framer-motion";
import { Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { Folder } from "../types/types";
import { FolderPickerDropdown } from "./FolderPickerDropdown";

interface BatchActionBarProps {
  count: number;
  folders: Folder[];
  currentFolderId: string | null;
  onMoveSelected: (folderId: string | null) => void;
  onDeleteSelected: () => void;
  onClear: () => void;
  isDeleting?: boolean;
}

/**
 * Floating action bar shown when documents are selected.
 * Provides batch move, delete, and deselect actions.
 */
export function BatchActionBar({
  count,
  folders,
  currentFolderId,
  onMoveSelected,
  onDeleteSelected,
  onClear,
  isDeleting = false,
}: BatchActionBarProps): React.ReactElement {
  return (
    <AnimatePresence>
      {count > 0 && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ type: "spring", damping: 22, stiffness: 300 }}
          className="fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-5 py-3 shadow-2xl"
        >
          <span className="text-sm font-medium text-[hsl(var(--foreground))]">
            {count} sélectionné{count > 1 ? "s" : ""}
          </span>

          <span className="h-5 w-px bg-[hsl(var(--border))]" />

          <FolderPickerDropdown
            folders={folders}
            onSelect={onMoveSelected}
            currentFolderId={currentFolderId}
          />

          <Button
            variant="destructive"
            size="sm"
            onClick={onDeleteSelected}
            disabled={isDeleting}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Supprimer
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onClear}
            aria-label="Tout désélectionner"
          >
            <X className="h-4 w-4" />
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
