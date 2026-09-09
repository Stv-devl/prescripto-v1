import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { serviceError } from "@/lib/errors";
import { err, ok } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import * as projectsService from "../services/projects.service";
import { useUploadStore } from "../stores/uploadStore";
import type {
  Document,
  DocumentList,
  Folder,
  FolderList,
  Project,
  ProjectList,
  UpdateProjectInput,
} from "../types/types";
import {
  useArchiveProject,
  useCreateFolder,
  useCreateProject,
  useDeleteDocument,
  useDeleteFolder,
  useDeleteProject,
  useDocuments,
  useFolders,
  useMoveDocument,
  useProject,
  useProjects,
  useToggleFavorite,
  useUpdateFolder,
  useUpdateProject,
  useUploadDocument,
  useUploadDocumentToFolder,
  useUploadFolder,
} from "./hooks";

vi.mock("../services/projects.service");

const PROCESSING_LIST: DocumentList = {
  documents: [
    {
      id: "d-1",
      project_id: "p-1",
      folder_id: null,
      filename: "cctp.pdf",
      type: "pdf",
      lot: "",
      phase: "",
      size: 10,
      status: "processing",
      created_at: "2026-09-01T00:00:00Z",
      updated_at: "2026-09-01T00:00:00Z",
    },
  ],
  total: 1,
};

function aFile(): File {
  return new File(["x"], "cctp.pdf", { type: "application/pdf" });
}

describe("useDocuments", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("exposes the document list itself, which is what the polling predicate reads", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      ok(PROCESSING_LIST),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDocuments("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(PROCESSING_LIST);
    });
    expect(result.current.data?.documents[0].status).toBe("processing");
  });

  it("reaches its error state when the list cannot be read", async () => {
    vi.mocked(projectsService.listDocuments).mockResolvedValue(
      err(serviceError("server_error", "HTTP 503")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDocuments("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

describe("the upload mutations", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
    useUploadStore.setState({ uploads: {} });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("marks the upload in error when the service refuses it", async () => {
    vi.mocked(projectsService.uploadDocumentWithProgress).mockResolvedValue(
      err(serviceError("validation_failed", "HTTP 422")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadDocument("p-1"), { wrapper });

    await result.current
      .mutateAsync({ file: aFile(), uploadId: "u-1" })
      .catch(() => undefined);

    await waitFor(() => {
      expect(useUploadStore.getState().uploads["u-1"]?.status).toBe("error");
    });
  });

  it("marks a folder upload in error when the service refuses it", async () => {
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      err(serviceError("validation_failed", "HTTP 422")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadDocumentToFolder("p-1"), {
      wrapper,
    });

    await result.current
      .mutateAsync({ file: aFile(), uploadId: "u-2", folderId: "f-1" })
      .catch(() => undefined);

    await waitFor(() => {
      expect(useUploadStore.getState().uploads["u-2"]?.status).toBe("error");
    });
  });
});

describe("useToggleFavorite", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not invalidate the project list when the update is refused", async () => {
    vi.mocked(projectsService.updateProject).mockResolvedValue(
      err(serviceError("forbidden", "HTTP 403")),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useToggleFavorite(), { wrapper });

    await result.current
      .mutateAsync({ projectId: "p-1", isFavorite: false })
      .catch(() => undefined);

    expect(invalidate).not.toHaveBeenCalled();
  });

  it("invalidates the project list once the favourite is toggled", async () => {
    vi.mocked(projectsService.updateProject).mockResolvedValue(
      ok({ id: "p-1", is_favorite: true } as Project),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useToggleFavorite(), { wrapper });

    await result.current.mutateAsync({ projectId: "p-1", isFavorite: false });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useArchiveProject", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not invalidate the project list when archiving is refused", async () => {
    vi.mocked(projectsService.updateProject).mockResolvedValue(
      err(serviceError("forbidden", "HTTP 403")),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useArchiveProject(), { wrapper });

    await result.current
      .mutateAsync({ projectId: "p-1", currentStatus: "active" })
      .catch(() => undefined);

    expect(invalidate).not.toHaveBeenCalled();
  });

  it("sends the flipped status the caller asked for", async () => {
    vi.mocked(projectsService.updateProject).mockResolvedValue(
      ok({ id: "p-1" } as Project),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useArchiveProject(), { wrapper });

    await result.current.mutateAsync({
      projectId: "p-1",
      currentStatus: "archived",
    });

    expect(projectsService.updateProject).toHaveBeenCalledWith("p-1", {
      status: "active",
    });
  });
});

describe("useUploadFolder", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
    useUploadStore.setState({ uploads: {} });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("marks the file that failed in error, not only the folder", async () => {
    vi.mocked(projectsService.createFolder).mockResolvedValue(
      ok({ id: "f-1", name: "Lot 3" } as Folder),
    );
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      err(serviceError("validation_failed", "HTTP 422")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    await result.current
      .mutateAsync({ folderName: "Lot 3", files: [aFile()] })
      .catch(() => undefined);

    await waitFor(() => {
      const entries = Object.values(useUploadStore.getState().uploads);
      expect(entries.map((e) => e.status)).toEqual(["error"]);
    });
  });

  it("surfaces a folder that could not be created instead of uploading into it", async () => {
    vi.mocked(projectsService.createFolder).mockResolvedValue(
      err(serviceError("conflict", "HTTP 409")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    await result.current
      .mutateAsync({ folderName: "Lot 3", files: [aFile()] })
      .catch(() => undefined);

    expect(projectsService.uploadDocumentToFolder).not.toHaveBeenCalled();
  });
});

describe("useProjects", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("exposes the project list returned by the service", async () => {
    const list: ProjectList = { projects: [{ id: "p-1" } as Project], total: 1 };
    vi.mocked(projectsService.listProjects).mockResolvedValue(ok(list));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjects(), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(list);
    });
  });
});

describe("useProject", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("exposes the single project returned by the service for the given id", async () => {
    const project = { id: "p-1", name: "Chantier LOOK" } as Project;
    vi.mocked(projectsService.getProject).mockResolvedValue(ok(project));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProject("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(project);
    });
  });
});

describe("useCreateProject", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates the projects list once a project is created", async () => {
    vi.mocked(projectsService.createProject).mockResolvedValue(
      ok({ id: "p-9" } as Project),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useCreateProject(), { wrapper });

    await result.current.mutateAsync({ name: "Chantier LOOK", phase: "" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useUpdateProject", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates both the project and the projects list once updated", async () => {
    vi.mocked(projectsService.updateProject).mockResolvedValue(
      ok({ id: "p-1" } as Project),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useUpdateProject("p-1"), { wrapper });

    await result.current.mutateAsync({ name: "Chantier LOOK" } as UpdateProjectInput);

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects", "p-1"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useDeleteProject", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates the projects list once a project is deleted", async () => {
    vi.mocked(projectsService.deleteProject).mockResolvedValue(ok(undefined));
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useDeleteProject(), { wrapper });

    await result.current.mutateAsync("p-1");

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["projects"] });
  });
});

describe("useDeleteDocument", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates the project's documents list once a document is deleted", async () => {
    vi.mocked(projectsService.deleteDocument).mockResolvedValue(ok(undefined));
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useDeleteDocument("p-1"), { wrapper });

    await result.current.mutateAsync("d-1");

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["documents", "p-1"] });
  });
});

describe("useMoveDocument", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates both the documents and the folders lists once a document is moved", async () => {
    vi.mocked(projectsService.moveDocument).mockResolvedValue(
      ok({ id: "d-1", folder_id: "f-1" } as Document),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useMoveDocument("p-1"), { wrapper });

    await result.current.mutateAsync({ documentId: "d-1", folderId: "f-1" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["documents", "p-1"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["folders", "p-1"] });
  });
});

describe("useFolders", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("exposes the folder list returned by the service", async () => {
    const list: FolderList = { folders: [{ id: "f-1" } as Folder], total: 1 };
    vi.mocked(projectsService.listFolders).mockResolvedValue(ok(list));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useFolders("p-1"), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(list);
    });
  });
});

describe("useCreateFolder", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates the folders list once a folder is created", async () => {
    vi.mocked(projectsService.createFolder).mockResolvedValue(
      ok({ id: "f-1" } as Folder),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useCreateFolder("p-1"), { wrapper });

    await result.current.mutateAsync({ name: "Lot 3", lot: "03", phase: "" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["folders", "p-1"] });
  });
});

describe("useUpdateFolder", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates the folders list once a folder is updated", async () => {
    vi.mocked(projectsService.updateFolder).mockResolvedValue(
      ok({ id: "f-1" } as Folder),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useUpdateFolder("p-1"), { wrapper });

    await result.current.mutateAsync({ folderId: "f-1", name: "Lot 3 bis" });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["folders", "p-1"] });
  });
});

describe("useDeleteFolder", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("invalidates both the folders and the documents lists once a folder is deleted", async () => {
    vi.mocked(projectsService.deleteFolder).mockResolvedValue(ok(undefined));
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useDeleteFolder("p-1"), { wrapper });

    await result.current.mutateAsync("f-1");

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["folders", "p-1"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["documents", "p-1"] });
  });
});
