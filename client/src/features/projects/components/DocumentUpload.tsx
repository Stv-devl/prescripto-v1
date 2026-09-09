import { Upload } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";
import { cn } from "@/lib/utils";
import { useUploadDocument, useUploadFolder } from "../hooks/hooks";
import { isSupportedFile, readDirectoryEntries } from "../utils/dragUtils";

interface DocumentUploadProps {
  projectId: string;
}

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "image/png",
  "image/jpeg",
  "image/webp",
  ".dwg",
  ".dxf",
];

export function DocumentUpload({ projectId }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument(projectId);
  const uploadFolder = useUploadFolder(projectId);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      Array.from(files).forEach((file) => {
        const uploadId = crypto.randomUUID();
        upload.mutate({ file, uploadId });
      });
    },
    [upload],
  );

  function onDragOver(e: DragEvent): void {
    e.preventDefault();
    setIsDragOver(true);
  }

  function onDragLeave(e: DragEvent): void {
    e.preventDefault();
    setIsDragOver(false);
  }

  async function onDrop(e: DragEvent): Promise<void> {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const items = e.dataTransfer.items;
    if (!items || items.length === 0) {
      handleFiles(e.dataTransfer.files);
      return;
    }

    const folderEntries: { name: string; entry: FileSystemDirectoryEntry }[] =
      [];
    const looseFiles: File[] = [];

    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.();
      if (entry?.isDirectory) {
        folderEntries.push({
          name: entry.name,
          entry: entry as FileSystemDirectoryEntry,
        });
      } else if (entry?.isFile) {
        const file = items[i].getAsFile();
        if (file) looseFiles.push(file);
      }
    }

    for (const { name, entry } of folderEntries) {
      const allFiles = await readDirectoryEntries(entry);
      const supported = allFiles.filter(isSupportedFile);
      if (supported.length > 0) {
        uploadFolder.mutate({ folderName: name, files: supported });
      }
    }

    if (looseFiles.length > 0) {
      looseFiles.forEach((file) => {
        const uploadId = crypto.randomUUID();
        upload.mutate({ file, uploadId });
      });
    }
  }

  return (
    <section>
      <div
        role="button"
        tabIndex={0}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
          isDragOver
            ? "border-[#FFC300] bg-[#FFC300]/5"
            : "border-[hsl(var(--border))] hover:border-[hsl(var(--muted-foreground))]",
        )}
      >
        <Upload
          className={cn(
            "h-8 w-8 text-muted-foreground",
            isDragOver && "text-[#FFC300] animate-bounce",
          )}
        />
        <p className="text-sm text-muted-foreground">
          Glissez-déposez des fichiers ou un dossier, ou cliquez pour ajouter
          des fichiers
        </p>
        <p className="text-xs text-muted-foreground">
          PDF, DOCX, XLSX, DWG, PNG, JPG, WEBP — 50 MB max
        </p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ACCEPTED_TYPES.join(",")}
          multiple
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    </section>
  );
}
