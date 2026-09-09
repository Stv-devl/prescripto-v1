import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface DocumentGridFolderCardActionsProps {
  onRenameFolder?: () => void;
  onDeleteFolder?: () => void;
}

/**
 * Rename/delete buttons of a `DocumentGridFolderCard`, revealed on card
 * hover — each rendered only if its handler is provided.
 */
export function DocumentGridFolderCardActions({
  onRenameFolder,
  onDeleteFolder,
}: DocumentGridFolderCardActionsProps): React.ReactElement {
  return (
    <div
      className="flex shrink-0 gap-0.5 opacity-0 transition-opacity group-hover:opacity-100"
      role="presentation"
      onClick={(e) => e.stopPropagation()}
    >
      {onRenameFolder && (
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onRenameFolder}
          aria-label="Renommer le dossier"
        >
          <Pencil className="h-3 w-3" />
        </Button>
      )}
      {onDeleteFolder && (
        <Button
          variant="ghost"
          size="icon"
          className="group h-6 w-6 hover:scale-110 transition-all"
          onClick={(e) => {
            e.stopPropagation();
            onDeleteFolder();
          }}
          aria-label="Supprimer le dossier"
        >
          <Trash2 className="h-3 w-3 text-muted-foreground group-hover:!text-red-500 transition-colors" />
        </Button>
      )}
    </div>
  );
}
