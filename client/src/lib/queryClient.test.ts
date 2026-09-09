import { describe, expect, it } from "vitest";
import { queryClient } from "./queryClient";
import { ServiceFailure } from "./result";
import type { ServiceError } from "./errors";

/**
 * The retry predicate, narrowed out of `RetryValue<Error>`.
 *
 * `getDefaultOptions().queries?.retry` is a union that also admits a number, so
 * it is not callable until the function case is proved.
 */
function retryPredicate(): (failureCount: number, error: Error) => boolean {
  const retry = queryClient.getDefaultOptions().queries?.retry;
  if (typeof retry !== "function") {
    throw new Error("the query retry policy is not a predicate");
  }
  return retry;
}

/** What React Query actually receives: `unwrap` throws this, never a raw error. */
function failureOf(code: ServiceError["code"], message: string): ServiceFailure {
  return new ServiceFailure({ code, message });
}

describe("the query retry policy", () => {
  it("does not replay a timeout, which would only double the wait", () => {
    const retry = retryPredicate();

    expect(retry(0, failureOf("timeout", "Request timed out"))).toBe(false);
  });

  it("still replays a connection failure once, as it did before", () => {
    const retry = retryPredicate();

    expect(retry(0, failureOf("network_error", "Failed to fetch"))).toBe(true);
  });

  it("still refuses to replay an answer the server already decided", () => {
    const retry = retryPredicate();

    expect(retry(0, failureOf("not_found", "Project not found"))).toBe(false);
  });

  it("never replays a refusal that came from the rate limit", () => {
    const retry = retryPredicate();

    expect(retry(0, failureOf("rate_limited", "too many requests"))).toBe(false);
  });

  it("gives up after one replay, whatever the code", () => {
    const retry = retryPredicate();

    expect(retry(1, failureOf("network_error", "Failed to fetch"))).toBe(false);
  });
});
