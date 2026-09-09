import { apiGet, apiPost } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type {
  BatchEnrichResponse,
  DuplicateResponse,
  PaginatedChunks,
  PlaygroundSearchRequest,
  PlaygroundSearchResponse,
  RechunkResponse,
  SectionNode,
  SemanticSearchRequest,
  SimilarChunkResult,
} from "../types/types";

/** Detect near-duplicate chunks within a document. */
export function detectDuplicates(
  projectId: string,
  documentId: string,
  threshold: number = 0.92,
): Promise<Result<DuplicateResponse>> {
  return attempt(() =>
    apiGet<DuplicateResponse>(
      `/admin/projects/${projectId}/documents/${documentId}/duplicates?threshold=${threshold}`,
    ),
  );
}

/** Run a semantic search in the admin playground. */
export function playgroundSearch(
  projectId: string,
  body: PlaygroundSearchRequest,
): Promise<Result<PlaygroundSearchResponse>> {
  return attempt(() =>
    apiPost<PlaygroundSearchResponse>(
      `/admin/projects/${projectId}/playground/search`,
      body,
    ),
  );
}

/** Re-chunk an entire document. */
export function rechunkDocument(
  projectId: string,
  documentId: string,
): Promise<Result<RechunkResponse>> {
  return attempt(() =>
    apiPost<RechunkResponse>(
      `/admin/projects/${projectId}/documents/${documentId}/rechunk`,
      {},
      { slow: true },
    ),
  );
}

/** Semantic search chunks via Qdrant. */
export function semanticSearchChunks(
  projectId: string,
  body: SemanticSearchRequest,
): Promise<Result<PaginatedChunks>> {
  return attempt(() =>
    apiPost<PaginatedChunks>(
      `/admin/projects/${projectId}/chunks/semantic-search`,
      body,
    ),
  );
}

/** Get hierarchical section tree. */
export function getSectionTree(
  projectId: string,
): Promise<Result<SectionNode[]>> {
  return attempt(() =>
    apiGet<SectionNode[]>(`/admin/projects/${projectId}/chunks/section-tree`),
  );
}

/** Find similar chunks to a given chunk. */
export function findSimilarChunks(
  projectId: string,
  chunkId: string,
  limit: number = 10,
): Promise<Result<SimilarChunkResult[]>> {
  return attempt(() =>
    apiGet<SimilarChunkResult[]>(
      `/admin/projects/${projectId}/chunks/${chunkId}/similar?limit=${limit}`,
    ),
  );
}

/** Batch enrich chunks without keywords. */
export function batchEnrichKeywords(
  projectId: string,
): Promise<Result<BatchEnrichResponse>> {
  return attempt(() =>
    apiPost<BatchEnrichResponse>(
      `/admin/projects/${projectId}/chunks/batch-enrich-keywords`,
      {},
      { slow: true },
    ),
  );
}
