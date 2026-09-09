import {
  isServiceError,
  serviceErrorFrom,
  type ErrorRefiner,
  type ServiceError,
} from "./errors";

/** The value every service returns. Never throws — the failure is data. */
export type Result<T, E = ServiceError> =
  | { success: true; data: T }
  | { success: false; error: E };

/** Builds a success result. */
export function ok<T>(data: T): Result<T> {
  return { success: true, data };
}

/** Builds a failure result. */
export function err<T = never>(error: ServiceError): Result<T> {
  return { success: false, error };
}

/**
 * Error thrown by `unwrap`. Carries the `ServiceError` so React Query's `error`
 * stays typed and the UI can branch on `error.code`.
 */
export class ServiceFailure extends Error {
  readonly serviceError: ServiceError;

  constructor(error: ServiceError) {
    super(error.message);
    this.name = "ServiceFailure";
    this.serviceError = error;
  }
}

/**
 * Unwraps a `Result<T>` for React Query: returns the data, or throws so that
 * `isError` and `error` fire.
 *
 * This is the one sanctioned throw in the codebase, and it lives in the hook
 * layer — services still never throw.
 */
export function unwrap<T>(result: Result<T>): T {
  if (result.success) return result.data;
  throw new ServiceFailure(result.error);
}

/**
 * Narrows whatever the UI layer holds to a `ServiceError`.
 *
 * Pure on purpose: `ErrorMessage` calls it on every render, so a `console.error`
 * here would turn one displayed error into a log loop. Failures are logged once,
 * where they are built.
 */
export function toServiceError(error: unknown): ServiceError {
  if (error instanceof ServiceFailure) return error.serviceError;
  if (isServiceError(error)) return error;
  return {
    code: "unknown_error",
    message: error instanceof Error ? error.message : String(error),
    cause: error,
  };
}

/**
 * Runs one transport call and turns whatever it throws into a failed `Result`.
 *
 * Every exported service function that returns a domain type goes through this,
 * which is what keeps the conversion written once, inside the coverage floor,
 * instead of copied into fifty-odd try/catch blocks.
 */
export async function attempt<T>(
  call: () => Promise<T>,
  refine?: ErrorRefiner,
): Promise<Result<T>> {
  try {
    return ok(await call());
  } catch (error) {
    return err(serviceErrorFrom(error, refine));
  }
}
