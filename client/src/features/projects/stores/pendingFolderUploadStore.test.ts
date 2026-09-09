import { beforeEach, describe, expect, it } from "vitest";

import { usePendingFolderUploadStore } from "./pendingFolderUploadStore";

const initialPendingFolderUpload = usePendingFolderUploadStore.getState();

function aFolder(): { folderName: string; files: File[] } {
  return {
    folderName: "Groupe Vinci — Lot 03",
    files: [new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf")],
  };
}

describe("pending folder upload store", () => {
  beforeEach(() => {
    usePendingFolderUploadStore.setState(initialPendingFolderUpload, true);
  });

  it("holds the folder name and its files until someone takes them", () => {
    usePendingFolderUploadStore.getState().setPending(aFolder());

    const pending = usePendingFolderUploadStore.getState().pending;
    expect(pending?.folderName).toBe("Groupe Vinci — Lot 03");
    expect(pending?.files.map((file) => file.name)).toEqual([
      "cctp-lot-03.pdf",
    ]);
  });

  it("holds nothing after a reset, so dropped files cannot reach the next tenant", () => {
    usePendingFolderUploadStore.getState().setPending(aFolder());

    usePendingFolderUploadStore.getState().reset();

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
  });

  it("hands the folder over once, so a second reader gets nothing", () => {
    usePendingFolderUploadStore.getState().setPending(aFolder());

    const first = usePendingFolderUploadStore.getState().consume();
    const second = usePendingFolderUploadStore.getState().consume();

    expect(first?.folderName).toBe("Groupe Vinci — Lot 03");
    expect(second).toBeNull();
  });

  it("hands over nothing when no folder is waiting", () => {
    expect(usePendingFolderUploadStore.getState().consume()).toBeNull();
  });

  it("survives a reset with nothing waiting", () => {
    expect(() => {
      usePendingFolderUploadStore.getState().reset();
    }).not.toThrow();
    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
  });
});
