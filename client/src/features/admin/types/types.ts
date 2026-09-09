export interface AdjacentChunk {
  id: string;
  position: number;
  page: number;
  text_preview: string;
  content_type: string | null;
}

export interface ChunkListItem {
  id: string;
  document_id: string;
  filename: string;
  text_preview: string;
  page: number;
  position: number;
  char_count: number | null;
  content_type: string | null;
  keywords: string[] | null;
  section_title: string | null;
  parent_sections: string[] | null;
  lot: string;
  phase: string;
  type: string;
  qdrant_point_id: string;
  created_at: string;
  quality_score: number | null;
}

export interface PaginatedChunks {
  items: ChunkListItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface ChunkDetail extends ChunkListItem {
  text: string;
  qdrant_payload: Record<string, unknown> | null;
  adjacent_chunks: AdjacentChunk[];
}

export interface DocumentStats {
  document_id: string;
  filename: string;
  type: string;
  lot: string;
  chunk_count: number;
  avg_char_count: number;
  min_char_count: number;
  max_char_count: number;
}

export interface QualityAlerts {
  chunks_without_keywords: number;
  chunks_heading_only: number;
  chunks_very_short: number;
  chunks_oversized: number;
  documents_with_errors: number;
}

export interface ChunkStatsResponse {
  total_chunks: number;
  total_documents: number;
  avg_quality_score: number;
  by_document: DocumentStats[];
  by_content_type: Record<string, number>;
  by_lot: Record<string, number>;
  by_type: Record<string, number>;
  size_distribution: Record<string, number>;
  quality_alerts: QualityAlerts;
}

export interface SyncDocumentItem {
  document_id: string;
  filename: string;
  sql_count: number;
  qdrant_count: number;
  status: string;
  missing_in_qdrant: string[];
}

export interface PaginatedSyncDocuments {
  items: SyncDocumentItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface SyncCheckResponse {
  total_sql: number;
  total_qdrant: number;
  synced: boolean;
  documents: PaginatedSyncDocuments;
}

export interface ChunkFilters {
  page: number;
  per_page: number;
  document_id?: string;
  lot?: string;
  type?: string;
  content_type?: string;
  min_chars?: number;
  max_chars?: number;
  has_keywords?: boolean;
  search?: string;
  sort_by: string;
  sort_order: string;
  orphan?: boolean;
  parent_section?: string;
}

// ── Duplicate detection types ──

export interface DuplicatePair {
  chunk_a_id: string;
  chunk_b_id: string;
  chunk_a_preview: string;
  chunk_b_preview: string;
  chunk_a_position: number;
  chunk_b_position: number;
  chunk_a_page: number;
  chunk_b_page: number;
  similarity: number;
}

export interface DuplicateResponse {
  pairs: DuplicatePair[];
  total_chunks_analyzed: number;
}

// ── Mutation types ──

export interface ChunkUpdateRequest {
  text: string;
}

export interface ChunkSplitRequest {
  split_position: number;
}

export interface ChunkMergeRequest {
  adjacent_chunk_id: string;
}

export interface ChunkMutationResponse {
  message: string;
  chunk_ids: string[];
}

export interface RechunkResponse {
  old_count: number;
  new_count: number;
  old_avg_chars: number;
  new_avg_chars: number;
  message: string;
}

// ── Playground types ──

export interface PlaygroundSearchRequest {
  query: string;
  lot?: string;
  content_type?: string;
  limit?: number;
}

export interface PlaygroundSearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  text_preview: string;
  text: string;
  score: number;
  page: number;
  position: number;
  lot: string;
  type: string;
  content_type: string | null;
  keywords: string[];
  section_title: string | null;
  parent_sections: string[];
  char_count: number;
  quality_score: number;
}

export interface PlaygroundSearchResponse {
  results: PlaygroundSearchResult[];
  query_time_ms: number;
  total_results: number;
}

// ── Advanced filter types ──

export interface SemanticSearchRequest {
  query: string;
  lot?: string;
  limit?: number;
}

export interface SectionNode {
  title: string;
  children: SectionNode[];
  chunk_count: number;
}

export interface SimilarChunkResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  text_preview: string;
  similarity: number;
  content_type: string | null;
  section_title: string | null;
}

export interface BatchEnrichResponse {
  updated_count: number;
  message: string;
}
