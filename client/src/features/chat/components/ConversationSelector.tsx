import { Plus, Trash2 } from "lucide-react";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import type { Conversation } from "../types/types";

interface ConversationSelectorProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  isPending: boolean;
}

/**
 * Compact dropdown selector for conversations.
 * Replaces ConversationSidebar for full-width tab layout.
 */
export function ConversationSelector({
  conversations,
  selectedId,
  onSelect,
  onNew,
  onDelete,
  isPending,
}: ConversationSelectorProps) {
  if (isPending) {
    return (
      <header className="flex items-center gap-2 border-b border-[hsl(var(--border))] px-4 py-2">
        <LoadingSpinner size="sm" />
      </header>
    );
  }

  return (
    <header className="flex items-center gap-2 border-b border-[hsl(var(--border))] px-4 py-2">
      <select
        value={selectedId ?? ""}
        onChange={(e) => {
          const value = e.target.value;
          if (value === "") {
            onNew();
          } else {
            onSelect(value);
          }
        }}
        className="flex-1 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-1.5 text-sm text-[hsl(var(--foreground))]"
        aria-label="Sélectionner une conversation"
      >
        <option value="">Nouvelle conversation</option>
        {conversations.map((conv) => (
          <option key={conv.id} value={conv.id}>
            {conv.title}
          </option>
        ))}
      </select>

      <Button
        variant="ghost"
        size="icon"
        onClick={onNew}
        aria-label="Nouvelle conversation"
        className="h-8 w-8 shrink-0"
      >
        <Plus className="h-4 w-4" />
      </Button>

      {selectedId && (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onDelete(selectedId)}
          aria-label="Supprimer la conversation"
          className="h-8 w-8 shrink-0 text-muted-foreground hover:text-red-400"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </header>
  );
}
