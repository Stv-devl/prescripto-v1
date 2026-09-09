/** Utilities for discriminating internal (document move) vs external (OS file) drag events. */

export const SUPPORTED_EXTENSIONS = new Set([
  ".pdf",
  ".docx",
  ".xlsx",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".dwg",
  ".dxf",
]);

function getFileExtension(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx >= 0 ? name.slice(idx).toLowerCase() : "";
}

/** Returns true if the file has a supported extension. */
export function isSupportedFile(file: File): boolean {
  return SUPPORTED_EXTENSIONS.has(getFileExtension(file.name));
}

/** Returns true if the drag event originates from the OS (files), not from an internal drag. */
export function isExternalFileDrop(e: React.DragEvent): boolean {
  return e.dataTransfer.types.includes("Files");
}

/** Extracts supported files from a drop event's dataTransfer. */
export function extractDroppedFiles(e: React.DragEvent): File[] {
  return Array.from(e.dataTransfer.files).filter(isSupportedFile);
}

/** Recursively reads all File objects from a FileSystemDirectoryEntry. */
export function readDirectoryEntries(
  dirEntry: FileSystemDirectoryEntry,
): Promise<File[]> {
  return new Promise((resolve, reject) => {
    const allFiles: File[] = [];
    const reader = dirEntry.createReader();

    function readBatch(): void {
      reader.readEntries(
        (entries) => {
          if (entries.length === 0) {
            resolve(allFiles);
            return;
          }

          const promises = entries.map((entry) => {
            if (entry.isFile) {
              return new Promise<void>((res) => {
                (entry as FileSystemFileEntry).file((f) => {
                  allFiles.push(f);
                  res();
                });
              });
            } else if (entry.isDirectory) {
              return readDirectoryEntries(
                entry as FileSystemDirectoryEntry,
              ).then((files) => {
                allFiles.push(...files);
              });
            }
            return Promise.resolve();
          });

          Promise.all(promises).then(() => readBatch());
        },
        (err) => reject(err),
      );
    }

    readBatch();
  });
}
