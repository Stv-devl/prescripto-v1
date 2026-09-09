import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface DocumentListFolderRowActionsProps {
  onRenameFolder?: () => void;
  onDeleteFolder?: () => void;
}

/** Rename/delete buttons of a `DocumentListFolderRow`, each rendered only if its handler is provided. */
export function DocumentListFolderRowActions({
  onRenameFolder,
  onDeleteFolder,
}: DocumentListFolderRowActionsProps): React.ReactElement {
  return (
    <span
      className="flex items-center justify-end gap-1"
      role="presentation"
      onClick={(e) => e.stopPropagation()}
    >
      {onRenameFolder && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-[hsl(var(--foreground))]"
          onClick={onRenameFolder}
          aria-label="Renommer le dossier"
        >
          <Pencil className="h-4 w-4" />
        </Button>
      )}
      {onDeleteFolder && (
        <Button
          variant="ghost"
          size="icon"
          className="group h-8 w-8 hover:scale-110 transition-all"
          onClick={(e) => {
            e.stopPropagation();
            onDeleteFolder();
          }}
          aria-label="Supprimer le dossier"
        >
          <Trash2 className="h-4 w-4 text-muted-foreground group-hover:!text-red-500 transition-colors" />
        </Button>
      )}
    </span>
  );
}
