import { serviceError, type ErrorRefiner } from "@/lib/errors";

/** Settings codes, on top of the canonical ones in `lib/errors.ts`. */
export type SettingsErrorCode = "invalid_current_password";

/**
 * Backend `detail` strings this feature recognises, matched **exactly** on the
 * lowercased text.
 *
 * Exact, never by substring: a message that merely contains a known phrase is
 * not the same answer, and substring matching is what this rewrite removed.
 */
const DETAIL_CODES: ReadonlyMap<string, SettingsErrorCode> = new Map([
  ["invalid current password", "invalid_current_password"],
]);

/** Refines a settings failure the status alone cannot tell apart. */
export const refineSettingsError: ErrorRefiner = (error) => {
  if (typeof error.detail !== "string") return null;

  const code = DETAIL_CODES.get(error.detail.toLowerCase());
  if (!code) return null;

  return serviceError(code, `HTTP ${error.status}: ${error.detail}`, error);
};
