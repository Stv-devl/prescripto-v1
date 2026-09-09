import { ChevronDown, FolderOpen, CornerLeftUp } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import type { Folder } from "../types/types";

interface FolderPickerDropdownProps {
  folders: Folder[];
  onSelect: (folderId: string | null) => void;
  currentFolderId?: string | null;
}

/**
 * Dropdown listing folders + "Racine" for moving documents.
 */
export function FolderPickerDropdown({
  folders,
  onSelect,
  currentFolderId = null,
}: FolderPickerDropdownProps): React.ReactElement {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  const availableFolders = folders.filter((f) => f.id !== currentFolderId);

  return (
    <div ref={ref} className="relative">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="gap-1.5"
      >
        <FolderOpen className="h-3.5 w-3.5" />
        Déplacer vers…
        <ChevronDown className="h-3 w-3" />
      </Button>

      {isOpen && (
        <div className="absolute bottom-full left-0 z-50 mb-1 min-w-[180px] rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] py-1 shadow-xl">
          {currentFolderId && (
            <button
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))]"
              onClick={() => {
                onSelect(null);
                setIsOpen(false);
              }}
            >
              <CornerLeftUp className="h-3.5 w-3.5 text-muted-foreground" />
              Racine
            </button>
          )}
          {availableFolders.map((folder) => (
            <button
              key={folder.id}
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))]"
              onClick={() => {
                onSelect(folder.id);
                setIsOpen(false);
              }}
            >
              <FolderOpen className="h-3.5 w-3.5 text-[#FFC300]" />
              {folder.name}
            </button>
          ))}
          {availableFolders.length === 0 && !currentFolderId && (
            <p className="px-3 py-2 text-xs text-muted-foreground">
              Aucun dossier disponible
            </p>
          )}
        </div>
      )}
    </div>
  );
}
