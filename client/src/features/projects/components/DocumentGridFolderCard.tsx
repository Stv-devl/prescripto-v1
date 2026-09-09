import { motion } from "framer-motion";
import { FolderOpen, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import type { useFolderDragDrop } from "../hooks/useFolderDragDrop";
import type { Document, Folder } from "../types/types";
import { DocumentGridFolderCardActions } from "./DocumentGridFolderCardActions";
import { InlineFolderRename } from "./InlineFolderRename";

interface DocumentGridFolderCardProps {
  folder: Folder;
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

/** One folder card of `DocumentGrid`. */
export function DocumentGridFolderCard({
  folder,
  editingFolderId,
  onStartRename,
  onCancelRename,
  onRenameFolder,
  isRenamingFolder,
  onDeleteFolder,
  onOpenFolder,
  onContextMenu,
  dd,
}: DocumentGridFolderCardProps): React.ReactElement {
  const isEditing = editingFolderId === folder.id;

  return (
    <motion.article
      key={`folder-${folder.id}`}
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "group relative flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 transition-colors",
        dd.dragOverFolderId === folder.id || dd.externalDragOverFolderId === folder.id
          ? "border-[#FFC300] bg-[#FFC300]/10"
          : "border-[hsl(var(--border))] bg-[hsl(var(--secondary))] hover:border-[#FFC300]/40",
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
      {/* Drop zone overlay text */}
      {dd.dragOverFolderId === folder.id && (
        <span className="absolute inset-0 flex items-center justify-center rounded-md text-xs font-medium text-[#FFC300]">
          Déposer ici
        </span>
      )}
      {dd.externalDragOverFolderId === folder.id && (
        <span className="absolute inset-0 flex items-center justify-center gap-1.5 rounded-md text-xs font-medium text-[#FFC300]">
          <Upload className="h-3.5 w-3.5 animate-bounce" />
          Ajouter au dossier
        </span>
      )}
      <FolderOpen className="h-5 w-5 shrink-0 text-[#FFC300]" />
      <div className="min-w-0 flex-1">
        {isEditing && onRenameFolder ? (
          <InlineFolderRename
            folder={folder}
            onRename={onRenameFolder}
            onCancel={onCancelRename}
            isRenaming={isRenamingFolder}
            variant="grid"
          />
        ) : (
          <div>
            <div className="flex items-baseline gap-1.5">
              <p className="truncate text-sm font-medium text-[hsl(var(--foreground))]">
                {folder.name}
              </p>
              <span className="shrink-0 text-[10px] text-muted-foreground">
                {folder.document_count}
              </span>
            </div>
            {(folder.lot || folder.phase) && (
              <p className="truncate text-[10px] text-muted-foreground">
                {[folder.lot, folder.phase].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
        )}
      </div>
      {!editingFolderId && (
        <DocumentGridFolderCardActions
          onRenameFolder={onRenameFolder ? () => onStartRename(folder.id) : undefined}
          onDeleteFolder={onDeleteFolder ? () => onDeleteFolder(folder) : undefined}
        />
      )}
    </motion.article>
  );
}
