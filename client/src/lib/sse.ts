import { HttpError, NetworkError } from "./errors";

/**
 * Reads a Server-Sent Events response and yields one parsed payload per event.
 *
 * The single SSE reader of this repository. Yields `unknown` on purpose:
 * validating a payload belongs to the schema of the feature owning the stream.
 *
 * @throws HttpError when the response carries a non-2xx status.
 * @throws NetworkError when the response carries no readable body.
 */
export async function* readSSE(response: Response): AsyncGenerator<unknown> {
  if (!response.ok) {
    throw new HttpError(response.status, await detailOf(response));
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new NetworkError("SSE response carried no body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;

        const payload = line.slice(6).trim();
        if (payload === "[DONE]") return;

        let parsed: unknown;
        try {
          parsed = JSON.parse(payload);
        } catch {
          continue;
        }

        yield parsed;
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
}

async function detailOf(response: Response): Promise<unknown> {
  const body: unknown = await response.json().catch(() => null);
  if (body !== null && typeof body === "object" && "detail" in body) {
    return (body as { detail: unknown }).detail;
  }
  return "Unknown error";
}
