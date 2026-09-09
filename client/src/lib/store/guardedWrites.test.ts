import { act, renderHook } from "@testing-library/react";
import {
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest";

import { useDeleteChunk } from "@/features/admin/hooks/hooks";
import * as adminService from "@/features/admin/services/admin.service";
import { useAdminStore } from "@/features/admin/stores/store";
import { useUploadFolder } from "@/features/projects/hooks/hooks";
import { useProjectsPageDrop } from "@/features/projects/hooks/useProjectsPageDrop";
import * as projectsService from "@/features/projects/services/projects.service";
import { usePendingFolderUploadStore } from "@/features/projects/stores/pendingFolderUploadStore";
import { useUploadStore } from "@/features/projects/stores/uploadStore";
import type {
  Document,
  Folder,
  Project,
} from "@/features/projects/types/types";
import * as dragUtils from "@/features/projects/utils/dragUtils";
import { err, ok } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { createQueryClientWrapper } from "@/test/utils";

const navigate = vi.fn();

vi.mock("@/features/projects/services/projects.service");
vi.mock("@/features/admin/services/admin.service");
vi.mock("@/features/projects/utils/dragUtils", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/projects/utils/dragUtils")>()),
  readDirectoryEntries: vi.fn(),
}));
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

// The drop handler's own parameter type, so the forged event stays assignable
// whatever the hook declares. Reading it here is a type query, not a contract.
type DropEvent = Parameters<
  ReturnType<typeof useProjectsPageDrop>["onDrop"]
>[0];

const FOLDER_NAME = "Groupe Vinci — Lot 03";

function droppedFolder(): DropEvent {
  const entry = { isDirectory: true, name: FOLDER_NAME };
  return {
    preventDefault: () => {},
    stopPropagation: () => {},
    dataTransfer: { items: [{ webkitGetAsEntry: () => entry }] },
  } as unknown as DropEvent;
}

function cctpFile(): File {
  return new File(["CCTP"], "cctp-lot-03.pdf", { type: "application/pdf" });
}

interface HeldCall<T> {
  started: Promise<void>;
  release: (value: T) => void;
  call: () => Promise<T>;
}

/** A service call the test can hold in flight and release on its own schedule. */
function heldInFlight<T>(): HeldCall<T> {
  let resolveInFlight: (value: T) => void = () => {};
  let markStarted: () => void = () => {};
  const inFlight = new Promise<T>((resolve) => {
    resolveInFlight = resolve;
  });
  const started = new Promise<void>((resolve) => {
    markStarted = resolve;
  });
  return {
    started,
    release: (value) => resolveInFlight(value),
    call: () => {
      markStarted();
      return inFlight;
    },
  };
}

// The setup file resets no store, and a Zustand store is a module singleton:
// capture the pristine state — actions included — before any case runs.
const initialAuth = useAuthStore.getState();
const initialPendingFolderUpload = usePendingFolderUploadStore.getState();
const initialUpload = useUploadStore.getState();

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState(initialAuth, true);
  usePendingFolderUploadStore.setState(initialPendingFolderUpload, true);
  useUploadStore.setState(initialUpload, true);
});

describe("dropping a folder while the session changes", () => {
  it("leaves no folder waiting to be consumed by the next tenant", async () => {
    const created = heldInFlight<Awaited<ReturnType<typeof projectsService.createProject>>>();
    vi.mocked(projectsService.createProject).mockImplementation(created.call);
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([cctpFile()]);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await created.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      created.release(ok({ id: "p-7" } as Project));
      await dropped;
    });

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
  });
});

describe("navigating after a folder drop while the session changes", () => {
  it("does not open the project created for the previous tenant", async () => {
    const created = heldInFlight<Awaited<ReturnType<typeof projectsService.createProject>>>();
    vi.mocked(projectsService.createProject).mockImplementation(created.call);
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([cctpFile()]);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await created.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      created.release(ok({ id: "p-7" } as Project));
      await dropped;
    });

    expect(navigate).not.toHaveBeenCalled();
  });
});

describe("uploading a folder while the session changes", () => {
  it("writes neither the folder row, nor the folder in progress, nor the file names", async () => {
    const folder = heldInFlight<Awaited<ReturnType<typeof projectsService.createFolder>>>();
    vi.mocked(projectsService.createFolder).mockImplementation(folder.call);
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      ok({ id: "d-1" } as Document),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    // Both writes are observed as they happen, not read at the end. The cache
    // entry is collected as soon as it loses its observer (gcTime: 0) and the
    // folder leaves the set after Promise.allSettled, unguarded — so the final
    // state is identical whether the guard held or not. What discriminates is
    // whether either ever existed.
    let folderRowWritten = false;
    const unsubscribeCache = queryClient.getQueryCache().subscribe(() => {
      if (queryClient.getQueryData(["folders", "p-1"]) !== undefined) {
        folderRowWritten = true;
      }
    });
    let everInProgress = false;
    const unsubscribe = useUploadStore.subscribe((state) => {
      if (state.uploadingFolderIds.size > 0) everInProgress = true;
    });
    onTestFinished(() => {
      unsubscribe();
      unsubscribeCache();
    });
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    const uploaded = result.current.mutateAsync({
      folderName: FOLDER_NAME,
      files: [cctpFile()],
    });
    await folder.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      folder.release(
        ok({ id: "f-1", project_id: "p-1", name: FOLDER_NAME } as Folder),
      );
      await uploaded;
    });
    expect(folderRowWritten).toBe(false);
    expect(everInProgress).toBe(false);
    expect(useUploadStore.getState().uploads).toEqual({});
  });
});

/**
 * The writes that land after an await and could carry the previous tenant's
 * data, grouped by the file they live in.
 *
 * - useProjectsPageDrop: the session probe before creating the project, then
 *   setPending + navigate — two calls, one of which wraps two statements.
 * - documentUploadHooks.ts (useUploadFolder): the folder cache row +
 *   addUploadingFolder, then addUpload per file.
 * - apiClient: renewTokens on a successful refresh, logout + redirect on a failed
 *   one, and the verdict that decides whether the original request is replayed.
 * - settings: the optimistic profile rollback.
 * - SessionProvider: the user a slow /auth/me answers with.
 */
const GUARDED_CALLS: Record<string, number> = {
  "/src/features/projects/hooks/useProjectsPageDrop.ts": 2,
  "/src/features/projects/hooks/documentUploadHooks.ts": 2,
  "/src/lib/apiClient.ts": 3,
  "/src/features/settings/hooks/hooks.ts": 1,
  "/src/providers/SessionProvider.tsx": 1,
  "/src/features/admin/hooks/hooks.ts": 1,
};

const sources: Record<string, string> = import.meta.glob(
  [
    "/src/features/projects/hooks/useProjectsPageDrop.ts",
    "/src/features/projects/hooks/documentUploadHooks.ts",
    "/src/lib/apiClient.ts",
    "/src/features/settings/hooks/hooks.ts",
    "/src/providers/SessionProvider.tsx",
    "/src/features/admin/hooks/hooks.ts",
  ],
  { query: "?raw", import: "default", eager: true },
);

describe("the inventory of guarded writes", () => {
  it("finds every file it claims to guard", () => {
    expect(Object.keys(sources).sort()).toEqual(
      Object.keys(GUARDED_CALLS).sort(),
    );
  });

  // Counts the text `inSession(`, so it sees a guard deleted but not one moved
  // out of the function it protects, nor a new unguarded write. The behaviour
  // cases carry those; the ESLint rule that would carry the third is out.
  it("keeps every file's guard count in step with the inventory", () => {
    const counted = Object.fromEntries(
      Object.entries(sources).map(([path, source]) => [
        path,
        source.split("inSession(").length - 1,
      ]),
    );

    expect(counted).toEqual(GUARDED_CALLS);
  });
});

describe("the same writes when the session holds", () => {
  it("arms the dropped files and opens the project it created", async () => {
    vi.mocked(projectsService.createProject).mockResolvedValue(
      ok({ id: "p-7" } as Project),
    );
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([cctpFile()]);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    await act(async () => {
      await result.current.onDrop(droppedFolder());
    });

    expect(usePendingFolderUploadStore.getState().pending?.folderName).toBe(
      FOLDER_NAME,
    );
    expect(navigate).toHaveBeenCalledWith("/projects/p-7");
  });

  it("writes the folder row, the folder in progress and the file names", async () => {
    vi.mocked(projectsService.createFolder).mockResolvedValue(
      ok({ id: "f-1", project_id: "p-1", name: FOLDER_NAME } as Folder),
    );
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      ok({ id: "d-1" } as Document),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    let folderRowWritten = false;
    const unsubscribeCache = queryClient.getQueryCache().subscribe(() => {
      if (queryClient.getQueryData(["folders", "p-1"]) !== undefined) {
        folderRowWritten = true;
      }
    });
    let everInProgress = false;
    const unsubscribe = useUploadStore.subscribe((state) => {
      if (state.uploadingFolderIds.size > 0) everInProgress = true;
    });
    onTestFinished(() => {
      unsubscribe();
      unsubscribeCache();
    });
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        folderName: FOLDER_NAME,
        files: [cctpFile()],
      });
    });
    expect(folderRowWritten).toBe(true);
    expect(everInProgress).toBe(true);
    expect(
      Object.values(useUploadStore.getState().uploads).map((u) => u.fileName),
    ).toEqual(["cctp-lot-03.pdf"]);
  });
});

describe("what a blocked write does not break", () => {
  it("still settles the folder upload, one outcome per file, instead of failing it", async () => {
    const folder = heldInFlight<
      Awaited<ReturnType<typeof projectsService.createFolder>>
    >();
    vi.mocked(projectsService.createFolder).mockImplementation(folder.call);
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      ok({ id: "d-1" } as Document),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    const uploaded = result.current.mutateAsync({
      folderName: FOLDER_NAME,
      files: [cctpFile(), cctpFile()],
    });
    await folder.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    let settled: PromiseSettledResult<unknown>[] = [];
    await act(async () => {
      folder.release(
        ok({ id: "f-1", project_id: "p-1", name: FOLDER_NAME } as Folder),
      );
      settled = await uploaded;
    });

    expect(result.current.isError).toBe(false);
    expect(settled).toHaveLength(2);
    expect(settled.every((outcome) => outcome.status === "fulfilled")).toBe(
      true,
    );
  });

  it("gives a mutation started after the boundary its own verdict", async () => {
    const first = heldInFlight<
      Awaited<ReturnType<typeof projectsService.createFolder>>
    >();
    vi.mocked(projectsService.createFolder).mockImplementation(first.call);
    vi.mocked(projectsService.uploadDocumentToFolder).mockResolvedValue(
      ok({ id: "d-1" } as Document),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUploadFolder("p-1"), { wrapper });

    const blocked = result.current.mutateAsync({
      folderName: FOLDER_NAME,
      files: [cctpFile()],
    });
    await first.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    vi.mocked(projectsService.createFolder).mockResolvedValue(
      ok({ id: "f-2", project_id: "p-1", name: "Lot 04" } as Folder),
    );
    await act(async () => {
      first.release(
        ok({ id: "f-1", project_id: "p-1", name: FOLDER_NAME } as Folder),
      );
      await blocked;
      await result.current.mutateAsync({
        folderName: "Lot 04",
        files: [cctpFile()],
      });
    });

    expect(
      Object.values(useUploadStore.getState().uploads).map((u) => u.folderId),
    ).toEqual(["f-2"]);
  });
});

describe("the other ways a session boundary is crossed", () => {
  it("holds the dropped files back on a logout, not only on a sign-in", async () => {
    const created = heldInFlight<
      Awaited<ReturnType<typeof projectsService.createProject>>
    >();
    vi.mocked(projectsService.createProject).mockImplementation(created.call);
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([cctpFile()]);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await created.started;
    act(() => {
      useAuthStore.getState().logout();
    });
    await act(async () => {
      created.release(ok({ id: "p-7" } as Project));
      await dropped;
    });

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("does not create a project for the previous tenant when the boundary falls while the folder is read", async () => {
    const read = heldInFlight<File[]>();
    vi.mocked(dragUtils.readDirectoryEntries).mockImplementation(read.call);
    vi.mocked(projectsService.createProject).mockResolvedValue(
      ok({ id: "p-7" } as Project),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await read.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      read.release([cctpFile()]);
      await dropped;
    });

    expect(projectsService.createProject).not.toHaveBeenCalled();
  });

  it("holds them back when the boundary falls while the folder is still being read", async () => {
    const read = heldInFlight<File[]>();
    vi.mocked(dragUtils.readDirectoryEntries).mockImplementation(read.call);
    vi.mocked(projectsService.createProject).mockResolvedValue(
      ok({ id: "p-7" } as Project),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await read.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      read.release([cctpFile()]);
      await dropped;
    });

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("stops showing the drop as still creating once the guard held it back", async () => {
    const created = heldInFlight<
      Awaited<ReturnType<typeof projectsService.createProject>>
    >();
    vi.mocked(projectsService.createProject).mockImplementation(created.call);
    vi.mocked(dragUtils.readDirectoryEntries).mockResolvedValue([cctpFile()]);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useProjectsPageDrop(), { wrapper });

    const dropped = result.current.onDrop(droppedFolder());
    await created.started;
    act(() => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
    });
    await act(async () => {
      created.release(ok({ id: "p-7" } as Project));
      await dropped;
    });

    expect(result.current.isCreating).toBe(false);
  });
});

describe("the admin action failure", () => {
  it("drops a failure that lands after the boundary, so the next session opens on a clean admin", async () => {
    const deleted = heldInFlight<
      Awaited<ReturnType<typeof adminService.deleteChunk>>
    >();
    vi.mocked(adminService.deleteChunk).mockImplementation(deleted.call);
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDeleteChunk("p-1"), { wrapper });

    act(() => {
      result.current.mutate("chunk-1");
    });
    await deleted.started;
    act(() => {
      useAuthStore.getState().logout();
    });
    await act(async () => {
      deleted.release(err({ code: "server_error", message: "delete failed" }));
    });

    expect(useAdminStore.getState().actionFailure).toBeNull();
  });
});
