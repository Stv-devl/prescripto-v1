import type { DragEvent } from "react";
import { describe, expect, it } from "vitest";
import {
  extractDroppedFiles,
  isExternalFileDrop,
  isSupportedFile,
  readDirectoryEntries,
} from "./dragUtils";

function fileNamed(name: string): File {
  return new File(["x"], name);
}

function dragEventWith(types: string[], files: File[]): DragEvent {
  return { dataTransfer: { types, files } } as unknown as DragEvent;
}

function fileEntry(name: string): FileSystemEntry {
  return {
    isFile: true,
    isDirectory: false,
    file: (onFile: (f: File) => void) => onFile(fileNamed(name)),
  } as unknown as FileSystemEntry;
}

function opaqueEntry(): FileSystemEntry {
  return { isFile: false, isDirectory: false } as unknown as FileSystemEntry;
}

function directoryOf(batches: FileSystemEntry[][]): FileSystemDirectoryEntry {
  let call = 0;
  return {
    isFile: false,
    isDirectory: true,
    createReader: () => ({
      readEntries: (onEntries: (entries: FileSystemEntry[]) => void) => {
        onEntries(batches[call++] ?? []);
      },
    }),
  } as unknown as FileSystemDirectoryEntry;
}

function failingDirectory(reason: Error): FileSystemDirectoryEntry {
  return {
    isFile: false,
    isDirectory: true,
    createReader: () => ({
      readEntries: (
        _onEntries: (entries: FileSystemEntry[]) => void,
        onError: (err: Error) => void,
      ) => onError(reason),
    }),
  } as unknown as FileSystemDirectoryEntry;
}

describe("isSupportedFile", () => {
  it("accepts a PDF", () => {
    expect(isSupportedFile(fileNamed("plan.pdf"))).toBe(true);
  });

  it("rejects an extension outside the supported list", () => {
    expect(isSupportedFile(fileNamed("payload.exe"))).toBe(false);
  });

  it("compares the extension in lower case", () => {
    expect(isSupportedFile(fileNamed("PLAN.PDF"))).toBe(true);
  });

  it("rejects a file with no extension", () => {
    expect(isSupportedFile(fileNamed("README"))).toBe(false);
  });

  it("accepts a file whose whole name is the extension", () => {
    expect(isSupportedFile(fileNamed(".pdf"))).toBe(true);
  });
});

describe("isExternalFileDrop", () => {
  it("recognises a drag coming from the operating system", () => {
    expect(isExternalFileDrop(dragEventWith(["Files"], []))).toBe(true);
  });

  it("rejects an internal drag carrying no files", () => {
    expect(isExternalFileDrop(dragEventWith(["text/plain"], []))).toBe(false);
  });
});

describe("extractDroppedFiles", () => {
  it("keeps only the files with a supported extension", () => {
    const event = dragEventWith(
      ["Files"],
      [fileNamed("plan.pdf"), fileNamed("payload.exe"), fileNamed("photo.png")],
    );

    expect(extractDroppedFiles(event).map((f) => f.name)).toEqual([
      "plan.pdf",
      "photo.png",
    ]);
  });

  it("returns an empty list when no dropped file is supported", () => {
    const event = dragEventWith(["Files"], [fileNamed("payload.exe")]);

    expect(extractDroppedFiles(event)).toEqual([]);
  });
});

describe("readDirectoryEntries", () => {
  it("returns the files of a flat directory", async () => {
    const dir = directoryOf([[fileEntry("a.pdf"), fileEntry("b.png")]]);

    const files = await readDirectoryEntries(dir);

    expect(files.map((f) => f.name)).toEqual(["a.pdf", "b.png"]);
  });

  it("keeps reading until a batch comes back empty", async () => {
    const dir = directoryOf([[fileEntry("a.pdf")], [fileEntry("b.png")]]);

    const files = await readDirectoryEntries(dir);

    expect(files.map((f) => f.name)).toEqual(["a.pdf", "b.png"]);
  });

  it("descends recursively into a subdirectory", async () => {
    const sub = directoryOf([[fileEntry("nested.pdf")]]);
    const dir = directoryOf([[fileEntry("top.pdf"), sub]]);

    const files = await readDirectoryEntries(dir);

    expect(files.map((f) => f.name).sort()).toEqual(["nested.pdf", "top.pdf"]);
  });

  it("returns an empty list for an empty directory", async () => {
    expect(await readDirectoryEntries(directoryOf([[]]))).toEqual([]);
  });

  it("ignores an entry that is neither a file nor a directory", async () => {
    const dir = directoryOf([[fileEntry("a.pdf"), opaqueEntry()]]);

    const files = await readDirectoryEntries(dir);

    expect(files.map((f) => f.name)).toEqual(["a.pdf"]);
  });

  it("rejects when the directory cannot be read", async () => {
    const reason = new Error("Directory read failed");

    await expect(readDirectoryEntries(failingDirectory(reason))).rejects.toBe(
      reason,
    );
  });
});
