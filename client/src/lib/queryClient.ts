import { QueryClient } from "@tanstack/react-query";
import { toServiceError } from "./result";

/**
 * Codes an automatic replay cannot improve — it only delays the error state.
 *
 * Most describe a decision the server already made. `timeout` is the other
 * kind: the answer is unknown, but the call already spent its whole deadline,
 * so replaying doubles the wait before the user learns anything. `rate_limited`
 * is worse than either: a replay spends another hit of the very quota that
 * produced the refusal, pushing the deadline further out. Absent on purpose:
 * `server_error` (the incident retrying exists for) and `network_error` (the
 * request did not get through, a replay may succeed).
 */
const NON_RETRYABLE: ReadonlySet<string> = new Set([
  "unauthorized",
  "forbidden",
  "not_found",
  "validation_failed",
  "conflict",
  "timeout",
  "rate_limited",
]);

function isNonRetryable(code: string): boolean {
  return NON_RETRYABLE.has(code) || code.endsWith("_not_found");
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: (failureCount, error) =>
        failureCount < 1 && !isNonRetryable(toServiceError(error).code),
      refetchOnWindowFocus: false,
    },
  },
});
