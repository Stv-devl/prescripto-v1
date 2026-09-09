import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  useBatchEnrichKeywords,
  useDeleteChunk,
  useMergeChunks,
  useRechunkDocument,
  useSplitChunk,
  useUpdateChunk,
} from "./hooks";
import * as adminService from "../services/admin.service";
import { useAdminStore } from "../stores/store";
import { err, ok } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";

vi.mock("../services/admin.service");

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

const initialAdmin = useAdminStore.getState();

beforeEach(() => {
  vi.clearAllMocks();
  useAdminStore.setState(initialAdmin, true);
});

describe("admin mutations — reporting", () => {
  it("keeps a different mutation's unacknowledged failure when this one succeeds", async () => {
    const deleted = heldInFlight<Awaited<ReturnType<typeof adminService.deleteChunk>>>();
    const updated = heldInFlight<Awaited<ReturnType<typeof adminService.updateChunk>>>();
    vi.mocked(adminService.deleteChunk).mockImplementation(deleted.call);
    vi.mocked(adminService.updateChunk).mockImplementation(updated.call);
    const { wrapper } = createQueryClientWrapper();

    const del = renderHook(() => useDeleteChunk("p-1"), { wrapper });
    const upd = renderHook(() => useUpdateChunk("p-1"), { wrapper });

    act(() => {
      del.result.current.mutate("chunk-1");
    });
    act(() => {
      upd.result.current.mutate({ chunkId: "chunk-2", body: { text: "x" } });
    });
    await deleted.started;
    await updated.started;

    await act(async () => {
      deleted.release(err({ code: "server_error", message: "delete failed" }));
    });
    await act(async () => {
      updated.release(ok({ message: "updated", chunk_ids: ["chunk-2"] }));
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("delete");
  });

  it("writes its own kind when useUpdateChunk fails", async () => {
    vi.mocked(adminService.updateChunk).mockResolvedValue(
      err({ code: "server_error", message: "update failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUpdateChunk("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate({ chunkId: "chunk-1", body: { text: "x" } });
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("update");
  });

  it("writes its own kind when useSplitChunk fails", async () => {
    vi.mocked(adminService.splitChunk).mockResolvedValue(
      err({ code: "server_error", message: "split failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useSplitChunk("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate({ chunkId: "chunk-1", body: { split_position: 10 } });
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("split");
  });

  it("writes its own kind when useMergeChunks fails", async () => {
    vi.mocked(adminService.mergeChunks).mockResolvedValue(
      err({ code: "server_error", message: "merge failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useMergeChunks("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate({ chunkId: "chunk-1", body: { adjacent_chunk_id: "chunk-2" } });
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("merge");
  });

  it("writes its own kind when useDeleteChunk fails", async () => {
    vi.mocked(adminService.deleteChunk).mockResolvedValue(
      err({ code: "server_error", message: "delete failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDeleteChunk("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate("chunk-1");
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("delete");
  });

  it("writes its own kind when useRechunkDocument fails", async () => {
    vi.mocked(adminService.rechunkDocument).mockResolvedValue(
      err({ code: "server_error", message: "rechunk failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useRechunkDocument("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate("doc-1");
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("rechunk");
  });

  it("writes kind enrich when useBatchEnrichKeywords fails", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      err({ code: "server_error", message: "enrich failed" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useBatchEnrichKeywords("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate(undefined);
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("enrich");
  });

  it("invalidates and does not write the slot when useBatchEnrichKeywords succeeds", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      ok({ updated_count: 3, message: "3 chunks enrichis" }),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useBatchEnrichKeywords("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate(undefined);
    });

    expect(useAdminStore.getState().actionFailure).toBeNull();
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["admin"] });
  });

  it("invalidates when the mutation fails too, and still reports the failure", async () => {
    vi.mocked(adminService.batchEnrichKeywords).mockResolvedValue(
      err({ code: "network_error", message: "Request timed out" }),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useBatchEnrichKeywords("p-1"), { wrapper });

    await act(async () => {
      result.current.mutate(undefined);
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("enrich");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["admin"] });
  });

  it("keeps the failure even when the failing mutation started after the succeeding one", async () => {
    const updated = heldInFlight<Awaited<ReturnType<typeof adminService.updateChunk>>>();
    const deleted = heldInFlight<Awaited<ReturnType<typeof adminService.deleteChunk>>>();
    vi.mocked(adminService.updateChunk).mockImplementation(updated.call);
    vi.mocked(adminService.deleteChunk).mockImplementation(deleted.call);
    const { wrapper } = createQueryClientWrapper();

    const upd = renderHook(() => useUpdateChunk("p-1"), { wrapper });
    const del = renderHook(() => useDeleteChunk("p-1"), { wrapper });

    act(() => {
      upd.result.current.mutate({ chunkId: "chunk-1", body: { text: "x" } });
    });
    act(() => {
      del.result.current.mutate("chunk-2");
    });
    await updated.started;
    await deleted.started;

    await act(async () => {
      deleted.release(err({ code: "server_error", message: "delete failed" }));
    });
    await act(async () => {
      updated.release(ok({ message: "updated", chunk_ids: ["chunk-1"] }));
    });

    expect(useAdminStore.getState().actionFailure?.kind).toBe("delete");
  });
});
