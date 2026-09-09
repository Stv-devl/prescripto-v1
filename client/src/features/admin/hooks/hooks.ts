import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import {
  beginSessionScope,
  type SessionScope,
} from "@/lib/store/sessionReset";
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
} from "../services/admin.service";
import { useAdminStore, type AdminActionKind } from "../stores/store";
import type {
  ChunkFilters,
  ChunkMergeRequest,
  ChunkSplitRequest,
  ChunkUpdateRequest,
  PlaygroundSearchRequest,
  SemanticSearchRequest,
} from "../types/types";

/** Fetch paginated chunk list with filters. */
export function useChunks(projectId: string, filters: ChunkFilters) {
  return useQuery({
    queryKey: ["admin", "chunks", projectId, filters],
    queryFn: async () => unwrap(await listChunks(projectId, filters)),
    enabled: !!projectId,
    placeholderData: (prev) => prev,
  });
}

/** Fetch chunk statistics for a project. */
export function useChunkStats(projectId: string) {
  return useQuery({
    queryKey: ["admin", "stats", projectId],
    queryFn: async () => unwrap(await getChunkStats(projectId)),
    enabled: !!projectId,
    staleTime: 30_000,
  });
}

/** Fetch full detail of a single chunk. */
export function useChunkDetail(projectId: string, chunkId: string | null) {
  return useQuery({
    queryKey: ["admin", "chunk", projectId, chunkId],
    queryFn: async () => unwrap(await getChunkDetail(projectId, chunkId!)),
    enabled: !!projectId && !!chunkId,
  });
}

/** Fetch all chunks of a document ordered by position. */
export function useDocumentChunks(projectId: string, documentId: string | null) {
  return useQuery({
    queryKey: ["admin", "document-chunks", projectId, documentId],
    queryFn: async () =>
      unwrap(await listDocumentChunks(projectId, documentId!)),
    enabled: !!projectId && !!documentId,
  });
}

/** Detect near-duplicate chunks within a document. */
export function useDuplicates(projectId: string, documentId: string | null, threshold: number = 0.92) {
  return useQuery({
    queryKey: ["admin", "duplicates", projectId, documentId, threshold],
    queryFn: async () =>
      unwrap(await detectDuplicates(projectId, documentId!, threshold)),
    enabled: !!projectId && !!documentId,
  });
}

/** Run a semantic search in the admin playground. */
export function usePlaygroundSearch(projectId: string) {
  return useMutation({
    mutationFn: async (body: PlaygroundSearchRequest) =>
      unwrap(await playgroundSearch(projectId, body)),
  });
}

// ── Mutation hooks ──

function useAdminInvalidation() {
  const queryClient = useQueryClient();
  return function invalidateAdmin(): void {
    queryClient.invalidateQueries({ queryKey: ["admin"] });
  };
}

/** What `onMutate` hands to `onError`: the session the action was started in. */
interface ActionScope {
  inSession: SessionScope;
}

/**
 * Opens an admin action: drops the now-stale previous report and captures the
 * session, before the first await.
 *
 * Nothing clears the slot on the way out — doing that only ever erased a
 * different mutation's still-unacknowledged failure.
 */
function openAction(): ActionScope {
  useAdminStore.getState().clearActionFailure();
  return { inSession: beginSessionScope() };
}

/**
 * The reporting callbacks every admin mutation shares.
 *
 * Refetching on `onSettled` rather than `onSuccess` is deliberate: a capped
 * write can time out on the client and still land on the server, and only a
 * refetch tells the screen which of the two happened.
 * @param projectId - Stored with the failure, so it cannot surface elsewhere.
 * @param kind - Which action this is, for the banner's French label.
 * @param invalidate - Refreshes the admin queries once the mutation settles.
 */
function reportingCallbacks(
  projectId: string,
  kind: AdminActionKind,
  invalidate: () => void,
) {
  return {
    onMutate: openAction,
    onSettled: invalidate,
    onError: (error: Error, _variables: unknown, context?: ActionScope) => {
      context?.inSession(() => {
        useAdminStore.getState().reportActionFailure(error, projectId, kind);
      });
    },
  };
}

/** Update a chunk's text and re-embed. */
export function useUpdateChunk(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async ({ chunkId, body }: { chunkId: string; body: ChunkUpdateRequest }) =>
      unwrap(await updateChunk(projectId, chunkId, body)),
    ...reportingCallbacks(projectId, "update", invalidate),
  });
}

/** Split a chunk at a character position. */
export function useSplitChunk(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async ({ chunkId, body }: { chunkId: string; body: ChunkSplitRequest }) =>
      unwrap(await splitChunk(projectId, chunkId, body)),
    ...reportingCallbacks(projectId, "split", invalidate),
  });
}

/** Merge a chunk with an adjacent chunk. */
export function useMergeChunks(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async ({ chunkId, body }: { chunkId: string; body: ChunkMergeRequest }) =>
      unwrap(await mergeChunks(projectId, chunkId, body)),
    ...reportingCallbacks(projectId, "merge", invalidate),
  });
}

/** Delete a chunk. */
export function useDeleteChunk(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async (chunkId: string) =>
      unwrap(await deleteChunk(projectId, chunkId)),
    ...reportingCallbacks(projectId, "delete", invalidate),
  });
}

/** Re-chunk an entire document. */
export function useRechunkDocument(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async (documentId: string) =>
      unwrap(await rechunkDocument(projectId, documentId)),
    ...reportingCallbacks(projectId, "rechunk", invalidate),
  });
}

// ── Advanced filter hooks ──

/** Semantic search for chunks. */
export function useSemanticSearch(projectId: string) {
  return useMutation({
    mutationFn: async (body: SemanticSearchRequest) =>
      unwrap(await semanticSearchChunks(projectId, body)),
  });
}

/** Fetch section tree. */
export function useSectionTree(projectId: string) {
  return useQuery({
    queryKey: ["admin", "section-tree", projectId],
    queryFn: async () => unwrap(await getSectionTree(projectId)),
    enabled: !!projectId,
    staleTime: 60_000,
  });
}

/** Find similar chunks. */
export function useSimilarChunks(projectId: string, chunkId: string | null) {
  return useQuery({
    queryKey: ["admin", "similar", projectId, chunkId],
    queryFn: async () => unwrap(await findSimilarChunks(projectId, chunkId!)),
    enabled: !!projectId && !!chunkId,
  });
}

/** Batch enrich chunks without keywords. */
export function useBatchEnrichKeywords(projectId: string) {
  const invalidate = useAdminInvalidation();
  return useMutation({
    mutationFn: async () => unwrap(await batchEnrichKeywords(projectId)),
    ...reportingCallbacks(projectId, "enrich", invalidate),
  });
}

/** Fetch SQL vs Qdrant sync check. */
export function useSyncCheck(
  projectId: string,
  page: number,
  perPage: number,
  onlyMismatches: boolean,
) {
  return useQuery({
    queryKey: ["admin", "sync", projectId, page, perPage, onlyMismatches],
    queryFn: async () =>
      unwrap(await getSyncCheck(projectId, page, perPage, onlyMismatches)),
    enabled: !!projectId,
  });
}
