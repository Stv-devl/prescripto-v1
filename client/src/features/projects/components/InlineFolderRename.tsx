import { Check, X } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import type { Folder } from "../types/types";

interface InlineFolderRenameProps {
  folder: Folder;
  onRename: (folderId: string, name: string) => void;
  onCancel: () => void;
  isRenaming: boolean;
  variant?: "list" | "grid";
}

export function InlineFolderRename({
  folder,
  onRename,
  onCancel,
  isRenaming,
  variant = "list",
}: InlineFolderRenameProps) {
  const [editName, setEditName] = useState(folder.name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleSubmit(): void {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== folder.name) {
      onRename(folder.id, trimmed);
    }
    onCancel();
  }

  function handleKeyDown(e: React.KeyboardEvent): void {
    if (e.key === "Enter") handleSubmit();
    if (e.key === "Escape") {
      setEditName(folder.name);
      onCancel();
    }
  }

  const Wrapper = variant === "list" ? "span" : "div";

  return (
    <Wrapper
      className={variant === "list" ? "inline-flex items-center gap-1" : "flex items-center gap-1"}
      onClick={(e) => e.stopPropagation()}
    >
      <input
        ref={inputRef}
        value={editName}
        onChange={(e) => setEditName(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleSubmit}
        className={`${variant === "list" ? "w-40" : "w-full"} rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-2 py-1 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:ring-1 focus:ring-[#FFC300]`}
        disabled={isRenaming}
      />
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={handleSubmit}
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
          onCancel();
        }}
      >
        <X className="h-3.5 w-3.5" />
      </Button>
    </Wrapper>
  );
}
