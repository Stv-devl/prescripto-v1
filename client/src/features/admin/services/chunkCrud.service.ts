import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type {
  ChunkDetail,
  ChunkFilters,
  ChunkListItem,
  ChunkMergeRequest,
  ChunkMutationResponse,
  ChunkSplitRequest,
  ChunkUpdateRequest,
  PaginatedChunks,
} from "../types/types";

function buildQueryString(filters: ChunkFilters): string {
  const params = new URLSearchParams();
  params.set("page", String(filters.page));
  params.set("per_page", String(filters.per_page));
  if (filters.document_id) params.set("document_id", filters.document_id);
  if (filters.lot) params.set("lot", filters.lot);
  if (filters.type) params.set("type", filters.type);
  if (filters.content_type) params.set("content_type", filters.content_type);
  if (filters.min_chars !== undefined) params.set("min_chars", String(filters.min_chars));
  if (filters.max_chars !== undefined) params.set("max_chars", String(filters.max_chars));
  if (filters.has_keywords !== undefined) params.set("has_keywords", String(filters.has_keywords));
  if (filters.search) params.set("search", filters.search);
  if (filters.orphan !== undefined) params.set("orphan", String(filters.orphan));
  if (filters.parent_section) params.set("parent_section", filters.parent_section);
  params.set("sort_by", filters.sort_by);
  params.set("sort_order", filters.sort_order);
  return params.toString();
}

/** List chunks with filters and pagination. */
export function listChunks(
  projectId: string,
  filters: ChunkFilters,
): Promise<Result<PaginatedChunks>> {
  return attempt(() =>
    apiGet<PaginatedChunks>(
      `/admin/projects/${projectId}/chunks?${buildQueryString(filters)}`,
    ),
  );
}

/** Get full detail of a single chunk. */
export function getChunkDetail(
  projectId: string,
  chunkId: string,
): Promise<Result<ChunkDetail>> {
  return attempt(() =>
    apiGet<ChunkDetail>(`/admin/projects/${projectId}/chunks/${chunkId}`),
  );
}

/** List all chunks of a document ordered by position. */
export function listDocumentChunks(
  projectId: string,
  documentId: string,
): Promise<Result<ChunkListItem[]>> {
  return attempt(() =>
    apiGet<ChunkListItem[]>(
      `/admin/projects/${projectId}/documents/${documentId}/chunks`,
    ),
  );
}

/** Update chunk text and re-embed. */
export function updateChunk(
  projectId: string,
  chunkId: string,
  body: ChunkUpdateRequest,
): Promise<Result<ChunkMutationResponse>> {
  return attempt(() =>
    apiPut<ChunkMutationResponse>(
      `/admin/projects/${projectId}/chunks/${chunkId}`,
      body,
    ),
  );
}

/** Split a chunk at a character position. */
export function splitChunk(
  projectId: string,
  chunkId: string,
  body: ChunkSplitRequest,
): Promise<Result<ChunkMutationResponse>> {
  return attempt(() =>
    apiPost<ChunkMutationResponse>(
      `/admin/projects/${projectId}/chunks/${chunkId}/split`,
      body,
    ),
  );
}

/** Merge a chunk with an adjacent chunk. */
export function mergeChunks(
  projectId: string,
  chunkId: string,
  body: ChunkMergeRequest,
): Promise<Result<ChunkMutationResponse>> {
  return attempt(() =>
    apiPost<ChunkMutationResponse>(
      `/admin/projects/${projectId}/chunks/${chunkId}/merge`,
      body,
    ),
  );
}

/** Delete a chunk from DB and Qdrant. */
export function deleteChunk(
  projectId: string,
  chunkId: string,
): Promise<Result<void>> {
  return attempt(() =>
    apiDelete(`/admin/projects/${projectId}/chunks/${chunkId}`),
  );
}
