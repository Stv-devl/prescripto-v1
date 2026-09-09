import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/apiClient";
import { HttpError } from "@/lib/errors";
import { ok } from "@/lib/result";
import type { ChunkFilters } from "../types/types";
import {
  batchEnrichKeywords,
  deleteChunk,
  detectDuplicates,
  findSimilarChunks,
  getChunkDetail,
  getChunkStats,
  getSectionTree,
  getSyncCheck,
  listChunks,
  listDocumentChunks,
  mergeChunks,
  playgroundSearch,
  rechunkDocument,
  semanticSearchChunks,
  splitChunk,
  updateChunk,
} from "./admin.service";

vi.mock("@/lib/apiClient");

const PAYLOAD = { id: "x-1", name: "relayed" };

const MINIMAL_FILTERS: ChunkFilters = {
  page: 1,
  per_page: 50,
  sort_by: "position",
  sort_order: "asc",
};

function queryOf(call: string): URLSearchParams {
  return new URLSearchParams(call.split("?")[1]);
}

describe("admin.service — every operation relays the transport payload", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);
    vi.mocked(apiPost).mockResolvedValue(PAYLOAD);
    vi.mocked(apiPut).mockResolvedValue(PAYLOAD);
    vi.mocked(apiDelete).mockResolvedValue(undefined);
  });

  it("relays the eight read operations", async () => {
    await expect(listChunks("p-1", MINIMAL_FILTERS)).resolves.toEqual(ok(PAYLOAD));
    await expect(getChunkStats("p-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(getChunkDetail("p-1", "c-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(listDocumentChunks("p-1", "d-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(detectDuplicates("p-1", "d-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(getSectionTree("p-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(findSimilarChunks("p-1", "c-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(getSyncCheck("p-1", 1, 20, false)).resolves.toEqual(ok(PAYLOAD));
  });

  it("targets one distinct path per read operation", async () => {
    await getChunkStats("p-1");
    await getChunkDetail("p-1", "c-1");
    await listDocumentChunks("p-1", "d-1");
    await getSectionTree("p-1");

    expect(vi.mocked(apiGet).mock.calls.map((c) => c[0])).toEqual([
      "/admin/projects/p-1/chunks/stats",
      "/admin/projects/p-1/chunks/c-1",
      "/admin/projects/p-1/documents/d-1/chunks",
      "/admin/projects/p-1/chunks/section-tree",
    ]);
  });

  it("posts each creating operation to its own path, carrying its body", async () => {
    await playgroundSearch("p-1", { query: "isolation", limit: 20 });
    await splitChunk("p-1", "c-1", { split_position: 120 });
    await mergeChunks("p-1", "c-1", { adjacent_chunk_id: "c-2" });
    await rechunkDocument("p-1", "d-1");
    await semanticSearchChunks("p-1", { query: "isolation" });
    await batchEnrichKeywords("p-1");

    expect(vi.mocked(apiPost).mock.calls).toEqual([
      [
        "/admin/projects/p-1/playground/search",
        { query: "isolation", limit: 20 },
      ],
      ["/admin/projects/p-1/chunks/c-1/split", { split_position: 120 }],
      ["/admin/projects/p-1/chunks/c-1/merge", { adjacent_chunk_id: "c-2" }],
      ["/admin/projects/p-1/documents/d-1/rechunk", {}, { slow: true }],
      ["/admin/projects/p-1/chunks/semantic-search", { query: "isolation" }],
      ["/admin/projects/p-1/chunks/batch-enrich-keywords", {}, { slow: true }],
    ]);
  });

  it("updates a chunk with PUT, not POST, carrying its body", async () => {
    await updateChunk("p-1", "c-1", { text: "corrigé" });

    expect(apiPut).toHaveBeenCalledWith("/admin/projects/p-1/chunks/c-1", {
      text: "corrigé",
    });
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("relays the seven write operations", async () => {
    await expect(
      playgroundSearch("p-1", { query: "isolation", limit: 20 }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(
      updateChunk("p-1", "c-1", { text: "corrigé" }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(
      splitChunk("p-1", "c-1", { split_position: 120 }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(
      mergeChunks("p-1", "c-1", { adjacent_chunk_id: "c-2" }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(rechunkDocument("p-1", "d-1")).resolves.toEqual(ok(PAYLOAD));
    await expect(
      semanticSearchChunks("p-1", { query: "isolation" }),
    ).resolves.toEqual(ok(PAYLOAD));
    await expect(batchEnrichKeywords("p-1")).resolves.toEqual(ok(PAYLOAD));
  });

  it("resolves without a value when deleting a chunk", async () => {
    await expect(deleteChunk("p-1", "c-1")).resolves.toEqual(ok(undefined));
    expect(apiDelete).toHaveBeenCalledWith("/admin/projects/p-1/chunks/c-1");
  });
});

describe("admin.service — query string composition", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);
  });

  it("composes the query string from the filters it was given", async () => {
    await listChunks("p-1", {
      ...MINIMAL_FILTERS,
      document_id: "d-1",
      lot: "Gros œuvre",
      type: "pdf",
      content_type: "specification",
      min_chars: 100,
      max_chars: 2500,
      has_keywords: true,
      search: "isolation",
      orphan: false,
      parent_section: "2.1",
    });

    const query = queryOf(vi.mocked(apiGet).mock.calls[0][0]);

    expect(Object.fromEntries(query)).toEqual({
      page: "1",
      per_page: "50",
      document_id: "d-1",
      lot: "Gros œuvre",
      type: "pdf",
      content_type: "specification",
      min_chars: "100",
      max_chars: "2500",
      has_keywords: "true",
      search: "isolation",
      orphan: "false",
      parent_section: "2.1",
      sort_by: "position",
      sort_order: "asc",
    });
  });

  it("omits the filters that were not supplied", async () => {
    await listChunks("p-1", MINIMAL_FILTERS);

    const query = queryOf(vi.mocked(apiGet).mock.calls[0][0]);

    expect(Object.fromEntries(query)).toEqual({
      page: "1",
      per_page: "50",
      sort_by: "position",
      sort_order: "asc",
    });
  });

  it("carries the pagination and the mismatch flag on the sync check", async () => {
    await getSyncCheck("p-1", 3, 25, true);

    const query = queryOf(vi.mocked(apiGet).mock.calls[0][0]);

    expect(Object.fromEntries(query)).toEqual({
      page: "3",
      per_page: "25",
      only_mismatches: "true",
    });
  });
});

describe("admin.service — default arguments", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiGet).mockResolvedValue(PAYLOAD);
  });

  it("applies the 0.92 duplicate threshold when none is supplied", async () => {
    await detectDuplicates("p-1", "d-1");

    expect(apiGet).toHaveBeenCalledWith(
      "/admin/projects/p-1/documents/d-1/duplicates?threshold=0.92",
    );
  });

  it("applies the supplied duplicate threshold when there is one", async () => {
    await detectDuplicates("p-1", "d-1", 0.75);

    expect(apiGet).toHaveBeenCalledWith(
      "/admin/projects/p-1/documents/d-1/duplicates?threshold=0.75",
    );
  });

  it("applies the limit of 10 similar chunks when none is supplied", async () => {
    await findSimilarChunks("p-1", "c-1");

    expect(apiGet).toHaveBeenCalledWith(
      "/admin/projects/p-1/chunks/c-1/similar?limit=10",
    );
  });

  it("applies the supplied limit of similar chunks when there is one", async () => {
    await findSimilarChunks("p-1", "c-1", 3);

    expect(apiGet).toHaveBeenCalledWith(
      "/admin/projects/p-1/chunks/c-1/similar?limit=3",
    );
  });
});

describe("admin.service — failures", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("surfaces a server failure on listChunks as a failed result, not an empty page", async () => {
    vi.mocked(apiGet).mockRejectedValue(
      new HttpError(500, "Internal Server Error"),
    );

    await expect(listChunks("p-1", MINIMAL_FILTERS)).resolves.toMatchObject({
      success: false,
      error: { code: "server_error" },
    });
  });

  it("surfaces a missing chunk on deleteChunk under its code", async () => {
    vi.mocked(apiDelete).mockRejectedValue(
      new HttpError(404, "Chunk not found"),
    );


    await expect(deleteChunk("p-1", "c-1")).resolves.toMatchObject({
      success: false,
      error: { code: "not_found" },
    });
  });
});
