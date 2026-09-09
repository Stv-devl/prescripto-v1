/**
 * Canonical error codes for the whole client.
 *
 * Features add their own in `features/<name>/services/<name>.errors.ts`; every
 * code declared anywhere gets a line in `src/lib/userMessages.ts`. Diverges
 * from `templates/lib-core.md` on purpose: no `db_error` (nothing here can
 * produce one), plus `forbidden` and `server_error`, which this backend does
 * return. Rationale: docs/work/service-result-error/plan.md.
 *
 * `network_error` and `timeout` are the two transport outcomes and they are not
 * interchangeable: `timeout` means the request was sent and no answer came in
 * time, so the server may have acted and a caller mutating state must treat the
 * outcome as unknown. `network_error` covers every other transport failure —
 * usually a request that never got through, but also an answer that arrived
 * unusable, such as a stream with no body (`lib/sse.ts`).
 */
export type ServiceErrorCode =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "validation_failed"
  | "conflict"
  | "server_error"
  | "network_error"
  | "timeout"
  | "rate_limited"
  | "unknown_error";

/**
 * The error every service returns inside `Result<T>`.
 *
 * `code` is stable and machine-readable — the only thing the UI branches on.
 * `message` is technical English, for logs, never rendered. `cause` is the raw
 * underlying error. Deliberately no `userMessage`: the UI picks its copy from
 * `code` through `userMessageFor`, so French lives in exactly one place.
 */
export interface ServiceError {
  code: ServiceErrorCode | (string & {});
  message: string;
  cause?: unknown;
}

/**
 * Thrown by `apiClient` when the server answered with a non-2xx status.
 *
 * Carries the status and the untouched body: a code cannot be derived from the
 * `detail` text alone, since this API returns `{"detail": "<string>"}` from its
 * own handlers and `{"detail": [ ... ]}` from FastAPI validation, same key.
 */
export class HttpError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`HTTP ${status}`);
    this.name = "HttpError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Thrown by `apiClient` when the transport failed.
 *
 * Its subclass `TimeoutError` narrows that to "we stopped waiting", so an
 * `instanceof NetworkError` check does NOT exclude a request the server may
 * have received and acted on.
 */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * Thrown by `apiClient` when a deadline fired.
 *
 * The request was sent and no answer came in time, so unlike a plain
 * `NetworkError` the server may have acted: a caller mutating state must treat
 * the outcome as unknown.
 */
export class TimeoutError extends NetworkError {
  constructor(message: string) {
    super(message);
    this.name = "TimeoutError";
  }
}

/**
 * Turns one `HttpError` into a feature-specific `ServiceError`, or returns
 * `null` to let the status decide.
 *
 * A feature passes this behaviour down to `attempt` rather than having `lib/`
 * import a feature, which the architecture forbids.
 */
export type ErrorRefiner = (error: HttpError) => ServiceError | null;

const STATUS_CODES: ReadonlyMap<number, ServiceErrorCode> = new Map([
  [400, "validation_failed"],
  [401, "unauthorized"],
  [403, "forbidden"],
  [404, "not_found"],
  [409, "conflict"],
  [422, "validation_failed"],
  [429, "rate_limited"],
]);

function codeForStatus(status: number): ServiceErrorCode {
  const mapped = STATUS_CODES.get(status);
  if (mapped) return mapped;
  return status >= 500 ? "server_error" : "unknown_error";
}

function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return `${detail.length} validation error(s)`;
  return "no detail";
}

/**
 * Builds a `ServiceError` and logs it in English. The only place a
 * `console.error` for a service failure belongs.
 */
export function serviceError(
  code: ServiceError["code"],
  message: string,
  cause?: unknown,
): ServiceError {
  console.error(`[${code}] ${message}`, cause ?? "");
  return { code, message, cause };
}

/** Formats a `ServiceError` for a log line. Never produces user-facing copy. */
export function formatServiceError(error: ServiceError): string {
  return `[${error.code}] ${error.message}`;
}

/** Narrows an unknown value to a `ServiceError`. */
export function isServiceError(value: unknown): value is ServiceError {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    "message" in value
  );
}

/**
 * Derives a `ServiceError` from whatever the transport threw, logging it once.
 *
 * The refiner is consulted before any status-derived error is built: building
 * one first and discarding it would log twice.
 */
export function serviceErrorFrom(
  error: unknown,
  refine?: ErrorRefiner,
): ServiceError {
  if (error instanceof HttpError) {
    const refined = refine?.(error);
    if (refined) return refined;
    return serviceError(
      codeForStatus(error.status),
      `HTTP ${error.status}: ${describeDetail(error.detail)}`,
      error,
    );
  }

  if (error instanceof TimeoutError) {
    return serviceError("timeout", error.message, error);
  }

  if (error instanceof NetworkError) {
    return serviceError("network_error", error.message, error);
  }

  if (isServiceError(error)) return error;

  return serviceError(
    "unknown_error",
    error instanceof Error ? error.message : String(error),
    error,
  );
}
