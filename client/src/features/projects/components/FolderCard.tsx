import { FolderOpen, Pencil, Trash2, Check, X } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import type { Folder } from "../types/types";

interface FolderCardProps {
  folder: Folder;
  onOpen: (folderId: string) => void;
  onRename: (folderId: string, name: string) => void;
  onDelete: (folder: Folder) => void;
  isRenaming: boolean;
}

export function FolderCard({
  folder,
  onOpen,
  onRename,
  onDelete,
  isRenaming,
}: FolderCardProps) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(folder.name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function handleSubmitRename(): void {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== folder.name) {
      onRename(folder.id, trimmed);
    }
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent): void {
    if (e.key === "Enter") handleSubmitRename();
    if (e.key === "Escape") {
      setEditName(folder.name);
      setEditing(false);
    }
  }

  return (
    <div
      className="group flex cursor-pointer items-center gap-3 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-4 transition-colors hover:border-[#FFC300]/40"
      onClick={() => {
        if (!editing) onOpen(folder.id);
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !editing) onOpen(folder.id);
      }}
    >
      <FolderOpen className="h-8 w-8 shrink-0 text-[#FFC300]" />

      <div className="min-w-0 flex-1">
        {editing ? (
          <div
            className="flex items-center gap-1"
            role="presentation"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleSubmitRename}
              className="w-full rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 py-1 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              disabled={isRenaming}
            />
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={handleSubmitRename}
              disabled={isRenaming}
            >
              <Check className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => {
                setEditName(folder.name);
                setEditing(false);
              }}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        ) : (
          <>
            <p className="truncate text-sm font-medium text-[hsl(var(--foreground))]">
              {folder.name}
            </p>
            <p className="text-xs text-muted-foreground">
              {folder.document_count} document
              {folder.document_count !== 1 ? "s" : ""}
            </p>
          </>
        )}
      </div>

      {!editing && (
        <div
          className="flex shrink-0 gap-1 opacity-0 transition-opacity group-hover:opacity-100"
          role="presentation"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => {
              setEditName(folder.name);
              setEditing(true);
            }}
            aria-label="Renommer le dossier"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-red-400 hover:text-red-300"
            onClick={() => onDelete(folder)}
            aria-label="Supprimer le dossier"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}
    </div>
  );
}
