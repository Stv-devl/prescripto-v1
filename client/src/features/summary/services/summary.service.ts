import { apiGet, fetchSSE } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import { readSSE } from "@/lib/sse";
import type {
  SummaryReadWire,
  SummaryRead,
  SummarySSEEvent,
  SummaryStatusRead,
} from "../types/types";
import { toProjectSummary, toSummaryStatus } from "./summary.mapper";
import { summarySSEEvent } from "./summary.schema";

/** Fetch summary generation status (has documents, has cached summary). */
export function getSummaryStatus(
  projectId: string,
): Promise<Result<SummaryStatusRead>> {
  return attempt(() =>
    apiGet<SummaryStatusRead>(`/projects/${projectId}/summary/status`),
  );
}

/** Fetch the cached project summary, crossed into the domain. */
export function getSummary(projectId: string): Promise<Result<SummaryRead>> {
  return attempt(async () => {
    const wire = await apiGet<SummaryReadWire>(`/projects/${projectId}/summary`);

    return {
      ...wire,
      status: toSummaryStatus(wire.status),
      data: wire.data == null ? null : toProjectSummary(wire.data),
    };
  });
}

/**
 * Trigger summary generation, returns a streaming Response (SSE).
 *
 * Stays outside `Result<T>`: it hands back a transport object, not a domain
 * type, so the caller reads `response.ok` itself.
 */
export function generateSummarySSE(projectId: string): Promise<Response> {
  return fetchSSE(`/projects/${projectId}/summary/generate`, {});
}

/**
 * Generation events, validated against the backend contract and crossed into
 * the domain. Throws on an event the contract does not name.
 */
export async function* streamSummary(
  projectId: string,
): AsyncGenerator<SummarySSEEvent> {
  const response = await generateSummarySSE(projectId);

  for await (const raw of readSSE(response)) {
    const event = summarySSEEvent.parse(raw);

    yield event.type === "complete"
      ? {
          type: "complete",
          summary: toProjectSummary(event.summary),
          status: event.status,
        }
      : event;
  }
}
