import { apiGet } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { SyncCheckResponse } from "../types/types";

/** Check SQL vs Qdrant sync status. */
export function getSyncCheck(
  projectId: string,
  page: number,
  perPage: number,
  onlyMismatches: boolean,
): Promise<Result<SyncCheckResponse>> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    only_mismatches: String(onlyMismatches),
  });
  return attempt(() =>
    apiGet<SyncCheckResponse>(
      `/admin/projects/${projectId}/sync-check?${params}`,
    ),
  );
}
