import type { ServiceErrorCode } from "@/lib/errors";
import { ServiceFailure } from "@/lib/result";
import type {
  ChunkDetail,
  ChunkListItem,
  ChunkStatsResponse,
  DuplicateResponse,
  PaginatedChunks,
  PlaygroundSearchResponse,
  SectionNode,
  SimilarChunkResult,
  SyncCheckResponse,
} from "./types/types";

/**
 * Builds the error React Query hands the UI: `unwrap` throws a `ServiceFailure`,
 * so `query.error` is one, and `ErrorMessage` reads the code out of it.
 */
export function failureWithCode(code: ServiceErrorCode): ServiceFailure {
  return new ServiceFailure({ code, message: `admin request failed: ${code}` });
}

export const chunkItem: ChunkListItem = {
  id: "chunk-1",
  document_id: "doc-1",
  filename: "CCTP-lot-3.pdf",
  text_preview: "Isolation thermique des murs extérieurs",
  page: 4,
  position: 12,
  char_count: 820,
  content_type: "specification",
  keywords: ["isolation", "murs"],
  section_title: "5.2 Isolation",
  parent_sections: ["5 Enveloppe"],
  lot: "03",
  phase: "execution",
  type: "cctp",
  qdrant_point_id: "point-1",
  created_at: "2026-09-01T10:00:00Z",
  quality_score: 0.82,
};

export const chunkPage: PaginatedChunks = {
  items: [chunkItem],
  total: 1,
  page: 1,
  per_page: 20,
  total_pages: 1,
};

export const emptyChunkPage: PaginatedChunks = {
  items: [],
  total: 0,
  page: 1,
  per_page: 20,
  total_pages: 0,
};

export const chunkDetail: ChunkDetail = {
  ...chunkItem,
  text: "Isolation thermique des murs extérieurs par l'intérieur, épaisseur 140 mm.",
  qdrant_payload: null,
  adjacent_chunks: [
    {
      id: "chunk-2",
      position: 13,
      page: 4,
      text_preview: "Doublage",
      content_type: "description",
    },
  ],
};

/** Stats with one keyword alert, so the batch-enrich button is rendered. */
export const stats: ChunkStatsResponse = {
  total_chunks: 128,
  total_documents: 2,
  avg_quality_score: 0.74,
  by_document: [
    {
      document_id: "doc-1",
      filename: "CCTP-lot-3.pdf",
      type: "cctp",
      lot: "03",
      chunk_count: 64,
      avg_char_count: 780,
      min_char_count: 120,
      max_char_count: 2100,
    },
    {
      document_id: "doc-2",
      filename: "CCTP-lot-5.pdf",
      type: "cctp",
      lot: "05",
      chunk_count: 64,
      avg_char_count: 810,
      min_char_count: 140,
      max_char_count: 2400,
    },
  ],
  by_content_type: { specification: 90, description: 38 },
  by_lot: { "03": 64, "05": 64 },
  by_type: { cctp: 128 },
  size_distribution: { "0-500": 20, "500-1500": 100, "1500+": 8 },
  quality_alerts: {
    chunks_without_keywords: 7,
    chunks_heading_only: 1,
    chunks_very_short: 2,
    chunks_oversized: 0,
    documents_with_errors: 0,
  },
};

export const syncCheck: SyncCheckResponse = {
  total_sql: 128,
  total_qdrant: 128,
  synced: true,
  documents: {
    items: [
      {
        document_id: "doc-1",
        filename: "CCTP-lot-3.pdf",
        sql_count: 64,
        qdrant_count: 64,
        status: "synced",
        missing_in_qdrant: [],
      },
    ],
    total: 1,
    page: 1,
    per_page: 20,
  },
};

export const sectionTree: SectionNode[] = [
  { title: "5 Enveloppe", chunk_count: 40, children: [] },
];

export const duplicates: DuplicateResponse = {
  pairs: [
    {
      chunk_a_id: "chunk-1",
      chunk_b_id: "chunk-2",
      chunk_a_preview: "Isolation thermique",
      chunk_b_preview: "Isolation thermique",
      chunk_a_position: 12,
      chunk_b_position: 13,
      chunk_a_page: 4,
      chunk_b_page: 4,
      similarity: 0.97,
    },
  ],
  total_chunks_analyzed: 64,
};

export const noDuplicates: DuplicateResponse = {
  pairs: [],
  total_chunks_analyzed: 64,
};

export const playgroundResults: PlaygroundSearchResponse = {
  results: [
    {
      chunk_id: "chunk-1",
      document_id: "doc-1",
      filename: "CCTP-lot-3.pdf",
      text: "Isolation thermique des murs extérieurs",
      text_preview: "Isolation thermique des murs extérieurs",
      score: 0.88,
      quality_score: 0.82,
      page: 4,
      position: 12,
      lot: "03",
      type: "cctp",
      content_type: "specification",
      section_title: "5.2 Isolation",
      parent_sections: ["5 Enveloppe"],
      keywords: ["isolation"],
      char_count: 820,
    },
  ],
  query_time_ms: 42,
  total_results: 1,
};

export const similarChunks: SimilarChunkResult[] = [
  {
    chunk_id: "chunk-9",
    document_id: "doc-1",
    filename: "CCTP-lot-3.pdf",
    text_preview: "Isolation des planchers bas",
    similarity: 0.91,
    content_type: "specification",
    section_title: "5.3 Planchers",
  },
];
