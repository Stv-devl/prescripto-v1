import { Edit3, Save, Scissors, Trash2, X } from "lucide-react";

interface ChunkDetailActionBarProps {
  isEditing: boolean;
  isMutating: boolean;
  isSaving: boolean;
  isSplitting: boolean;
  isDeleting: boolean;
  canSave: boolean;
  showDeleteConfirm: boolean;
  onStartEdit: () => void;
  onSave: () => void;
  onSplit: () => void;
  onCancelEdit: () => void;
  onShowDeleteConfirmChange: (show: boolean) => void;
  onDelete: () => void;
}

export function ChunkDetailActionBar({
  isEditing,
  isMutating,
  isSaving,
  isSplitting,
  isDeleting,
  canSave,
  showDeleteConfirm,
  onStartEdit,
  onSave,
  onSplit,
  onCancelEdit,
  onShowDeleteConfirmChange,
  onDelete,
}: ChunkDetailActionBarProps) {
  return (
    <div className="flex items-center gap-2">
      {!isEditing ? (
        <button
          onClick={onStartEdit}
          disabled={isMutating}
          className="flex items-center gap-1.5 rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-xs transition-colors hover:border-[#FFC300]/50 hover:text-[#FFC300] disabled:opacity-50"
        >
          <Edit3 className="h-3.5 w-3.5" />
          Éditer
        </button>
      ) : (
        <>
          <button
            onClick={onSave}
            disabled={isMutating || !canSave}
            className="flex items-center gap-1.5 rounded-md bg-[#FFC300] px-3 py-1.5 text-xs font-medium text-[#1C1C1C] transition-colors hover:bg-[#FFC300]/90 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {isSaving ? "..." : "Sauvegarder"}
          </button>
          <button
            onClick={onSplit}
            disabled={isMutating}
            title="Placer le curseur dans le texte pour définir le point de coupure"
            className="flex items-center gap-1.5 rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-xs transition-colors hover:border-blue-500/50 hover:text-blue-400 disabled:opacity-50"
          >
            <Scissors className="h-3.5 w-3.5" />
            {isSplitting ? "..." : "Scinder"}
          </button>
          <button
            onClick={onCancelEdit}
            className="flex items-center gap-1.5 rounded-md border border-[hsl(var(--border))] px-3 py-1.5 text-xs transition-colors hover:border-red-500/50 hover:text-red-400"
          >
            <X className="h-3.5 w-3.5" />
            Annuler
          </button>
        </>
      )}

      <div className="ml-auto">
        {!showDeleteConfirm ? (
          <button
            onClick={() => onShowDeleteConfirmChange(true)}
            disabled={isMutating}
            aria-label="Supprimer le chunk"
            className="flex items-center gap-1 rounded-md px-2 py-1.5 text-xs text-red-400 transition-colors hover:bg-red-500/10 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button
              onClick={onDelete}
              disabled={isMutating}
              className="rounded-md bg-red-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              {isDeleting ? "..." : "Supprimer"}
            </button>
            <button
              onClick={() => onShowDeleteConfirmChange(false)}
              className="rounded-md px-2 py-1 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            >
              Non
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
