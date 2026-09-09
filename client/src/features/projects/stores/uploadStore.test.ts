import { beforeEach, describe, expect, it } from "vitest";

import { useUploadStore } from "./uploadStore";

const initialUpload = useUploadStore.getState();

describe("upload store", () => {
  beforeEach(() => {
    useUploadStore.setState(initialUpload, true);
  });

  it("holds no upload and no uploading folder after a reset", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf", "folder-77");
    useUploadStore.getState().addUploadingFolder("folder-77");

    useUploadStore.getState().reset();

    expect(useUploadStore.getState().uploads).toEqual({});
    expect(useUploadStore.getState().uploadingFolderIds.size).toBe(0);
  });

  it("hands out a fresh folder set on reset, so two sessions never share one", () => {
    useUploadStore.getState().reset();
    const firstSession = useUploadStore.getState().uploadingFolderIds;
    firstSession.add("folder-77");

    useUploadStore.getState().reset();

    expect(useUploadStore.getState().uploadingFolderIds.size).toBe(0);
  });

  it("hands out a fresh uploads object on reset, so two sessions never share one", () => {
    useUploadStore.getState().reset();
    const firstSession = useUploadStore.getState().uploads;
    firstSession["leaked"] = {
      fileName: "cctp-lot-03.pdf",
      progress: 0,
      status: "uploading",
      folderId: null,
      resolvedDocId: null,
    };

    useUploadStore.getState().reset();

    expect(useUploadStore.getState().uploads).toEqual({});
  });

  it("records a file as uploading, with the folder it came from", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf", "folder-77");

    expect(useUploadStore.getState().uploads["up-1"]).toEqual({
      fileName: "cctp-lot-03.pdf",
      progress: 0,
      status: "uploading",
      folderId: "folder-77",
      resolvedDocId: null,
    });
  });

  it("updates progress, status and resolved document on the targeted upload only", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf");
    useUploadStore.getState().addUpload("up-2", "dpgf-lot-03.xlsx");

    useUploadStore.getState().setProgress("up-1", 42);
    useUploadStore.getState().setStatus("up-1", "processing");
    useUploadStore.getState().setResolved("up-1", "doc-1");

    expect(useUploadStore.getState().uploads["up-1"]?.progress).toBe(42);
    expect(useUploadStore.getState().uploads["up-1"]?.status).toBe("processing");
    expect(useUploadStore.getState().uploads["up-1"]?.resolvedDocId).toBe("doc-1");
    expect(useUploadStore.getState().uploads["up-2"]).toEqual({
      fileName: "dpgf-lot-03.xlsx",
      progress: 0,
      status: "uploading",
      folderId: null,
      resolvedDocId: null,
    });
  });

  it("drops the targeted upload and keeps the others", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf");
    useUploadStore.getState().addUpload("up-2", "dpgf-lot-03.xlsx");

    useUploadStore.getState().removeUpload("up-1");

    expect(Object.keys(useUploadStore.getState().uploads)).toEqual(["up-2"]);
  });

  it("tracks and untracks a folder being uploaded", () => {
    useUploadStore.getState().addUploadingFolder("folder-77");
    expect(useUploadStore.getState().uploadingFolderIds.has("folder-77")).toBe(true);

    useUploadStore.getState().removeUploadingFolder("folder-77");
    expect(useUploadStore.getState().uploadingFolderIds.has("folder-77")).toBe(false);
  });

  it("records a file with no folder when none is given", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf");

    expect(useUploadStore.getState().uploads["up-1"]?.folderId).toBeNull();
  });

  it("ignores a removal aimed at an upload that is not there", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf");

    useUploadStore.getState().removeUpload("up-gone");

    expect(Object.keys(useUploadStore.getState().uploads)).toEqual(["up-1"]);
  });

  it("ignores progress, status and resolution aimed at an upload that is not there", () => {
    useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf");

    useUploadStore.getState().setProgress("up-gone", 99);
    useUploadStore.getState().setStatus("up-gone", "ready");
    useUploadStore.getState().setResolved("up-gone", "doc-gone");

    expect(Object.keys(useUploadStore.getState().uploads)).toEqual(["up-1"]);
    expect(useUploadStore.getState().uploads["up-1"]?.progress).toBe(0);
  });

  it("survives a reset with nothing in flight", () => {
    useUploadStore.getState().reset();

    expect(useUploadStore.getState().uploads).toEqual({});
    expect(useUploadStore.getState().uploadingFolderIds.size).toBe(0);
  });
});
