import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpError, NetworkError } from "@/lib/errors";
import { ok } from "@/lib/result";
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  uploadFile,
  uploadFileWithProgress,
  uploadFileWithProgressAndFields,
} from "@/lib/apiClient";
import {
  createFolder,
  createProject,
  deleteDocument,
  deleteFolder,
  deleteProject,
  getProject,
  listDocuments,
  listFolders,
  listProjects,
  moveDocument,
  updateFolder,
  updateProject,
  uploadDocument,
  uploadDocumentToFolder,
  uploadDocumentWithProgress,
} from "./projects.service";

vi.mock("@/lib/apiClient");

const PAYLOAD = { id: "x-1", name: "relayed" };

function aFile(): File {
  return new File(["contents"], "cctp.pdf");
}

describe("projects.service — projects", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("relays what the transport returns for each read", async () => {
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);

    await expect(listProjects()).resolves.toEqual(ok(PAYLOAD));
    await expect(getProject("p-1")).resolves.toEqual(ok(PAYLOAD));

    expect(apiGet).toHaveBeenNthCalledWith(1, "/projects");
    expect(apiGet).toHaveBeenNthCalledWith(2, "/projects/p-1");
  });

  it("relays what the transport returns for each write", async () => {
    vi.mocked(apiPost).mockResolvedValue(PAYLOAD);
    vi.mocked(apiPatch).mockResolvedValue(PAYLOAD);
    vi.mocked(apiDelete).mockResolvedValue(undefined);

    await expect(createProject({ name: "Villa", phase: "APS" })).resolves.toEqual(ok(PAYLOAD));
    await expect(updateProject("p-1", { name: "Villa 2" })).resolves.toEqual(
      ok(PAYLOAD),
    );
    await expect(deleteProject("p-1")).resolves.toEqual(ok(undefined));

    expect(apiPost).toHaveBeenCalledWith("/projects", {
      name: "Villa",
      phase: "APS",
    });
    expect(apiPatch).toHaveBeenCalledWith("/projects/p-1", { name: "Villa 2" });
    expect(apiDelete).toHaveBeenCalledWith("/projects/p-1");
  });

  it("surfaces an unavailable backend on listProjects as a failed result, not an empty list", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.mocked(apiGet).mockRejectedValue(
      new HttpError(503, "Service Unavailable"),
    );

    await expect(listProjects()).resolves.toMatchObject({
      success: false,
      error: { code: "server_error" },
    });
  });
});

describe("projects.service — folders", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("relays what the transport returns for each folder operation", async () => {
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);
    vi.mocked(apiPost).mockResolvedValue(PAYLOAD);
    vi.mocked(apiPatch).mockResolvedValue(PAYLOAD);
    vi.mocked(apiDelete).mockResolvedValue(undefined);

    await expect(listFolders("p-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(
      createFolder("p-1", { name: "Plans", lot: "Gros œuvre", phase: "APS" }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(updateFolder("f-1", { lot: "Gros œuvre" })).resolves.toEqual(
      ok(PAYLOAD),
    );
    await expect(deleteFolder("f-1")).resolves.toEqual(ok(undefined));

    expect(apiGet).toHaveBeenCalledWith("/projects/p-1/folders");
    expect(apiPost).toHaveBeenCalledWith("/projects/p-1/folders", {
      name: "Plans",
      lot: "Gros œuvre",
      phase: "APS",
    });
    expect(apiPatch).toHaveBeenCalledWith("/folders/f-1", {
      lot: "Gros œuvre",
    });
    expect(apiDelete).toHaveBeenCalledWith("/folders/f-1");
  });
});

describe("projects.service — documents", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("targets the documents endpoint for each of the three upload paths", async () => {
    const file = aFile();
    const onProgress = (): void => {};
    vi.mocked(uploadFile).mockResolvedValue(PAYLOAD);
    vi.mocked(uploadFileWithProgress).mockResolvedValue(PAYLOAD);
    vi.mocked(uploadFileWithProgressAndFields).mockResolvedValue(PAYLOAD);

    await uploadDocument("p-1", file);
    await uploadDocumentWithProgress("p-1", file, onProgress);
    await uploadDocumentToFolder("p-1", file, "f-3", onProgress);

    expect(uploadFile).toHaveBeenCalledWith("/projects/p-1/documents", file);
    expect(uploadFileWithProgress).toHaveBeenCalledWith(
      "/projects/p-1/documents",
      file,
      onProgress,
    );
    expect(uploadFileWithProgressAndFields).toHaveBeenCalledWith(
      "/projects/p-1/documents",
      file,
      { folder_id: "f-3" },
      onProgress,
    );
  });

  it("relays what the transport returns for each document operation", async () => {
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    vi.mocked(uploadFile).mockResolvedValue(PAYLOAD);

    await expect(listDocuments("p-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(deleteDocument("d-1")).resolves.toEqual(ok(undefined));
    await expect(uploadDocument("p-1", aFile())).resolves.toEqual(ok(PAYLOAD));

    expect(apiGet).toHaveBeenCalledWith("/projects/p-1/documents");
    expect(apiDelete).toHaveBeenCalledWith("/documents/d-1");
  });

  it("sends the folder identifier when moving a document into a folder", async () => {
    vi.mocked(apiPatch).mockResolvedValue(PAYLOAD);

    await moveDocument("d-1", "f-9");

    expect(apiPatch).toHaveBeenCalledWith("/documents/d-1/move", {
      folder_id: "f-9",
    });
  });

  it("sends a null folder identifier, which is what moves a document back to the root", async () => {
    vi.mocked(apiPatch).mockResolvedValue(PAYLOAD);

    await moveDocument("d-1", null);

    expect(apiPatch).toHaveBeenCalledWith("/documents/d-1/move", {
      folder_id: null,
    });
  });

  it("returns the moved document in the success branch, root move included", async () => {
    vi.mocked(apiPatch).mockResolvedValue(PAYLOAD);

    await expect(moveDocument("d-1", null)).resolves.toEqual(ok(PAYLOAD));
  });

  it("relays every progress step to the callback it was given", async () => {
    const seen: number[] = [];
    vi.mocked(uploadFileWithProgress).mockImplementation(
      async (_path, _file, onProgress) => {
        onProgress(10);
        onProgress(70);
        onProgress(100);
        return PAYLOAD;
      },
    );

    await uploadDocumentWithProgress("p-1", aFile(), (p) => seen.push(p));

    expect(seen).toEqual([10, 70, 100]);
  });

  it("attaches the folder identifier to the upload fields", async () => {
    vi.mocked(uploadFileWithProgressAndFields).mockResolvedValue(PAYLOAD);
    const onProgress = (): void => {};
    const file = aFile();

    await uploadDocumentToFolder("p-1", file, "f-3", onProgress);

    expect(uploadFileWithProgressAndFields).toHaveBeenCalledWith(
      "/projects/p-1/documents",
      file,
      { folder_id: "f-3" },
      onProgress,
    );
  });

  it("surfaces an upload failure under its own code, and reports no progress after it", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const seen: number[] = [];
    vi.mocked(uploadFileWithProgress).mockImplementation(
      async (_path, _file, onProgress) => {
        onProgress(40);
        throw new NetworkError("Network error during upload");
      },
    );

    await expect(
      uploadDocumentWithProgress("p-1", aFile(), (p) => seen.push(p)),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "network_error" },
    });
    expect(seen).toEqual([40]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });
});
