import { beforeEach, describe, expect, it } from "vitest";

import { useAdminStore } from "./store";

const initialAdmin = useAdminStore.getState();

describe("admin chunks store", () => {
  beforeEach(() => {
    useAdminStore.setState(initialAdmin, true);
  });

  it("returns filters, chunk, tab and document to their starting values on reset", () => {
    useAdminStore.getState().setFilter("search", "Groupe Vinci");
    useAdminStore.getState().selectChunk("chunk-9");
    useAdminStore.getState().setActiveTab("table");
    useAdminStore.getState().setSelectedDocument("doc-1");

    useAdminStore.getState().reset();

    expect(useAdminStore.getState().filters).toEqual({
      page: 1,
      per_page: 50,
      sort_by: "position",
      sort_order: "asc",
    });
    expect(useAdminStore.getState().selectedChunkId).toBeNull();
    expect(useAdminStore.getState().activeTab).toBe("dashboard");
    expect(useAdminStore.getState().selectedDocumentId).toBeNull();
  });

  it("hands out a fresh filters object on reset, so two sessions never share one", () => {
    useAdminStore.getState().reset();
    const first = useAdminStore.getState().filters;
    first.per_page = 999;

    useAdminStore.getState().reset();

    expect(useAdminStore.getState().filters.per_page).toBe(50);
  });

  it("returns only the filters on a filters reset, leaving the tab and both selections", () => {
    useAdminStore.getState().setFilter("search", "Groupe Vinci");
    useAdminStore.getState().selectChunk("chunk-9");
    useAdminStore.getState().setActiveTab("table");
    useAdminStore.getState().setSelectedDocument("doc-1");

    useAdminStore.getState().resetFilters();

    expect(useAdminStore.getState().filters.search).toBeUndefined();
    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-9");
    expect(useAdminStore.getState().activeTab).toBe("table");
    expect(useAdminStore.getState().selectedDocumentId).toBe("doc-1");
  });

  it("goes back to the first page when a filter other than the page changes", () => {
    useAdminStore.getState().setFilter("page", 4);
    expect(useAdminStore.getState().filters.page).toBe(4);

    useAdminStore.getState().setFilter("lot", "03");

    expect(useAdminStore.getState().filters.lot).toBe("03");
    expect(useAdminStore.getState().filters.page).toBe(1);
  });

  it("keeps the page it is given when the page itself is the filter that changes", () => {
    useAdminStore.getState().setFilter("page", 4);

    expect(useAdminStore.getState().filters.page).toBe(4);
  });

  it("goes back to the first page when a batch of filters changes without one", () => {
    useAdminStore.getState().setFilter("page", 4);

    useAdminStore.getState().setFilters({ lot: "03", type: "cctp" });

    expect(useAdminStore.getState().filters.lot).toBe("03");
    expect(useAdminStore.getState().filters.type).toBe("cctp");
    expect(useAdminStore.getState().filters.page).toBe(1);
  });

  it("keeps the page a batch of filters carries", () => {
    useAdminStore.getState().setFilters({ lot: "03", page: 7 });

    expect(useAdminStore.getState().filters.page).toBe(7);
  });

  it("drops tenant-bearing filters on reset", () => {
    useAdminStore.getState().setFilter("search", "Groupe Vinci");
    useAdminStore.getState().setFilter("document_id", "doc-vinci-1");

    useAdminStore.getState().reset();

    expect(useAdminStore.getState().filters.search).toBeUndefined();
    expect(useAdminStore.getState().filters.document_id).toBeUndefined();
  });

  it("takes the chunk, the tab and the document as given", () => {
    useAdminStore.getState().selectChunk("chunk-9");
    useAdminStore.getState().setActiveTab("playground");
    useAdminStore.getState().setSelectedDocument("doc-1");

    expect(useAdminStore.getState().selectedChunkId).toBe("chunk-9");
    expect(useAdminStore.getState().activeTab).toBe("playground");
    expect(useAdminStore.getState().selectedDocumentId).toBe("doc-1");
  });

  it("lets a chunk and a document selection be dropped", () => {
    useAdminStore.getState().selectChunk("chunk-9");
    useAdminStore.getState().setSelectedDocument("doc-1");

    useAdminStore.getState().selectChunk(null);
    useAdminStore.getState().setSelectedDocument(null);

    expect(useAdminStore.getState().selectedChunkId).toBeNull();
    expect(useAdminStore.getState().selectedDocumentId).toBeNull();
  });
});

describe("admin chunks store — action failure reporting", () => {
  beforeEach(() => {
    useAdminStore.setState(initialAdmin, true);
  });

  it("keeps the claim count above zero when two claimants have each claimed and only one has released", () => {
    useAdminStore.getState().claimActionFailure();
    useAdminStore.getState().claimActionFailure();

    useAdminStore.getState().releaseActionFailure();

    expect(useAdminStore.getState().actionFailureClaimants).toBeGreaterThan(0);
  });

  it("returns the claim count to zero after a single claim is released", () => {
    useAdminStore.getState().claimActionFailure();

    useAdminStore.getState().releaseActionFailure();

    expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
  });

  it("stores the action kind exactly as reported", () => {
    const error = new Error("split failed");

    useAdminStore.getState().reportActionFailure(error, "p-1", "split");

    expect(useAdminStore.getState().actionFailure).toEqual({
      error,
      projectId: "p-1",
      kind: "split",
    });
  });

  it("resets the claim count to zero when a new failure is reported", () => {
    useAdminStore.getState().claimActionFailure();

    useAdminStore.getState().reportActionFailure(new Error("x"), "p-1", "delete");

    expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
  });

  it("returns the claim count to zero after two claims are each released, in either order", () => {
    useAdminStore.getState().claimActionFailure();
    useAdminStore.getState().claimActionFailure();

    useAdminStore.getState().releaseActionFailure();
    useAdminStore.getState().releaseActionFailure();

    expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
  });

  it("does not let the claim count go negative when released without a prior claim", () => {
    useAdminStore.getState().releaseActionFailure();

    expect(useAdminStore.getState().actionFailureClaimants).toBe(0);
  });
});
