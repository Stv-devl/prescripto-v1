import { motion } from "framer-motion";
import { FolderOpen, Upload } from "lucide-react";
import { cn, relativeTime } from "@/lib/utils";
import type { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import { DocumentListFolderRowActions } from "./DocumentListFolderRowActions";
import { InlineFolderRename } from "./InlineFolderRename";

interface DocumentListFolderRowProps {
  folder: Folder;
  hasSelection: boolean;
  editingFolderId: string | null;
  onStartRename: (id: string) => void;
  onCancelRename: () => void;
  onRenameFolder?: (folderId: string, name: string) => void;
  isRenamingFolder: boolean;
  onDeleteFolder?: (folder: Folder) => void;
  onOpenFolder?: (folderId: string) => void;
  onContextMenu?: (
    e: React.MouseEvent,
    target: { type: "document"; item: Document } | { type: "folder"; item: Folder },
  ) => void;
  dd: Pick<
    ReturnType<typeof useFolderDragDrop>,
    | "dragOverFolderId"
    | "externalDragOverFolderId"
    | "handleFolderDragOver"
    | "handleFolderDrop"
    | "handleFolderDragLeave"
  >;
}

/** One folder row of `DocumentList`'s table. */
export function DocumentListFolderRow({
  folder,
  hasSelection,
  editingFolderId,
  onStartRename,
  onCancelRename,
  onRenameFolder,
  isRenamingFolder,
  onDeleteFolder,
  onOpenFolder,
  onContextMenu,
  dd,
}: DocumentListFolderRowProps): React.ReactElement {
  const isEditing = editingFolderId === folder.id;

  return (
    <motion.tr
      layout
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "border-b border-[hsl(var(--border))] transition-colors cursor-pointer",
        dd.dragOverFolderId === folder.id || dd.externalDragOverFolderId === folder.id
          ? "border-[#FFC300] bg-[#FFC300]/10"
          : "hover:bg-[hsl(var(--muted))]",
      )}
      onClick={() => {
        if (!editingFolderId && onOpenFolder) onOpenFolder(folder.id);
      }}
      onContextMenu={(e) => {
        if (onContextMenu) {
          e.preventDefault();
          onContextMenu(e as unknown as React.MouseEvent, {
            type: "folder",
            item: folder,
          });
        }
      }}
      onDragOver={(e) => dd.handleFolderDragOver(e as unknown as React.DragEvent, folder.id)}
      onDrop={(e) => dd.handleFolderDrop(e as unknown as React.DragEvent, folder.id)}
      onDragLeave={dd.handleFolderDragLeave}
    >
      {hasSelection && <td className="w-10 py-3 pr-2" />}
      <td className="py-3 pr-4 font-medium">
        {isEditing && onRenameFolder ? (
          <InlineFolderRename
            folder={folder}
            onRename={onRenameFolder}
            onCancel={onCancelRename}
            isRenaming={isRenamingFolder}
            variant="list"
          />
        ) : (
          <span className="inline-flex items-center gap-2">
            {dd.externalDragOverFolderId === folder.id ? (
              <>
                <Upload className="h-4 w-4 shrink-0 text-[#FFC300] animate-bounce" />
                <span className="text-[#FFC300] font-medium">Ajouter au dossier</span>
              </>
            ) : (
              <>
                <FolderOpen className="h-4 w-4 shrink-0 text-[#FFC300]" />
                {folder.name}
              </>
            )}
          </span>
        )}
      </td>
      <td className="py-3 pr-4 text-muted-foreground">
        {folder.document_count} doc
        {folder.document_count !== 1 ? "s" : ""}
      </td>
      <td className="py-3 pr-4 text-muted-foreground">{folder.lot || "—"}</td>
      <td className="py-3 pr-4 text-muted-foreground">{folder.phase || "—"}</td>
      <td className="py-3 pr-4 text-muted-foreground">—</td>
      <td className="py-3 pr-4 text-muted-foreground">—</td>
      <td
        className="py-3 pr-4 text-muted-foreground text-xs"
        title={new Date(folder.created_at).toLocaleString("fr-FR")}
      >
        {relativeTime(folder.created_at)}
      </td>
      <td className="py-3">
        <DocumentListFolderRowActions
          onRenameFolder={onRenameFolder ? () => onStartRename(folder.id) : undefined}
          onDeleteFolder={onDeleteFolder ? () => onDeleteFolder(folder) : undefined}
        />
      </td>
    </motion.tr>
  );
}
