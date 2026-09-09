import { FolderOpen, Info, Pencil, Tags, Trash2 } from "lucide-react";
import type { ContextMenuItem } from "@/components/ui/ContextMenu";
import type { Document, Folder } from "@/features/projects";

export type ContextMenuTarget =
  | { type: "document"; item: Document }
  | { type: "folder"; item: Folder };

interface WorkspaceContextMenuCallbacks {
  onPreviewDocChange: (doc: Document | null) => void;
  onToggleSelect: (id: string) => void;
  selectedIds: Set<string>;
  onDeleteTargetChange: (doc: Document | null) => void;
  onEditingFolderIdChange: (id: string | null) => void;
  onEditFolderTargetChange: (folder: Folder | null) => void;
  onDeleteFolderTargetChange: (folder: Folder | null) => void;
}

/** The right-click menu items for a document or folder card in the workspace. */
export function getWorkspaceContextMenuItems(
  contextMenu: {
    position: { x: number; y: number };
    target: ContextMenuTarget;
  } | null,
  callbacks: WorkspaceContextMenuCallbacks,
): ContextMenuItem[] {
  if (!contextMenu) return [];

  if (contextMenu.target.type === "document") {
    const doc = contextMenu.target.item;
    return [
      {
        label: "Infos",
        icon: <Info className="h-4 w-4" />,
        onClick: () => callbacks.onPreviewDocChange(doc),
      },
      {
        label: "Déplacer vers…",
        icon: <FolderOpen className="h-4 w-4" />,
        onClick: () => {
          if (!callbacks.selectedIds.has(doc.id)) callbacks.onToggleSelect(doc.id);
        },
      },
      {
        label: "Supprimer",
        icon: <Trash2 className="h-4 w-4" />,
        onClick: () => callbacks.onDeleteTargetChange(doc),
        variant: "destructive",
      },
    ];
  }

  const folder = contextMenu.target.item;
  return [
    {
      label: "Renommer",
      icon: <Pencil className="h-4 w-4" />,
      onClick: () => callbacks.onEditingFolderIdChange(folder.id),
    },
    {
      label: "Lot / Phase",
      icon: <Tags className="h-4 w-4" />,
      onClick: () => callbacks.onEditFolderTargetChange(folder),
    },
    {
      label: "Supprimer",
      icon: <Trash2 className="h-4 w-4" />,
      onClick: () => callbacks.onDeleteFolderTargetChange(folder),
      variant: "destructive",
    },
  ];
}
