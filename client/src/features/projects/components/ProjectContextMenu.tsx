import { MoreVertical, ExternalLink, Archive, ArchiveRestore, Trash2 } from "lucide-react";
import { useState, useRef } from "react";
import { ContextMenu, type ContextMenuItem } from "@/components/ui/ContextMenu";
import type { Project } from "../types/types";

interface ProjectContextMenuProps {
  project: Project;
  onOpen: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

export function ProjectContextMenu({
  project,
  onOpen,
  onArchive,
  onDelete,
}: ProjectContextMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);

  function handleClick(e: React.MouseEvent): void {
    e.preventDefault();
    e.stopPropagation();
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPosition({ x: rect.right - 192, y: rect.bottom + 4 });
    }
    setIsOpen(true);
  }

  const isArchived = project.status === "archived";

  const items: ContextMenuItem[] = [
    {
      label: "Ouvrir",
      icon: <ExternalLink className="h-4 w-4" />,
      onClick: () => {
        onOpen();
      },
    },
    {
      label: isArchived ? "Désarchiver" : "Archiver",
      icon: isArchived ? (
        <ArchiveRestore className="h-4 w-4" />
      ) : (
        <Archive className="h-4 w-4" />
      ),
      onClick: () => {
        onArchive();
      },
    },
    {
      label: "Supprimer",
      icon: <Trash2 className="h-4 w-4" />,
      onClick: () => {
        onDelete();
      },
      variant: "destructive",
    },
  ];

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleClick}
        className="rounded p-1 text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
        aria-label="Actions du projet"
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      <ContextMenu
        isOpen={isOpen}
        position={position}
        items={items}
        onClose={() => setIsOpen(false)}
      />
    </>
  );
}
