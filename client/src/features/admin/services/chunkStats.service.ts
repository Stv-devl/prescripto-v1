import { apiGet } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { ChunkStatsResponse } from "../types/types";

/** Get chunk statistics for a project. */
export function getChunkStats(
  projectId: string,
): Promise<Result<ChunkStatsResponse>> {
  return attempt(() =>
    apiGet<ChunkStatsResponse>(`/admin/projects/${projectId}/chunks/stats`),
  );
}
