import { serviceError, type ErrorRefiner } from "@/lib/errors";

/** Auth codes, on top of the canonical ones in `lib/errors.ts`. */
export type AuthErrorCode =
  | "invalid_credentials"
  | "invalid_reset_token"
  | "email_already_registered";

/**
 * Backend `detail` strings this feature recognises, matched **exactly** on the
 * lowercased text.
 *
 * Exact, never by substring: a message that merely contains a known phrase is
 * not the same answer, and substring matching is what this rewrite removed.
 */
const DETAIL_CODES: ReadonlyMap<string, AuthErrorCode> = new Map([
  ["invalid login credentials", "invalid_credentials"],
  ["invalid reset token", "invalid_reset_token"],
  ["email already registered", "email_already_registered"],
]);

/** Refines an auth failure the status alone cannot tell apart. */
export const refineAuthError: ErrorRefiner = (error) => {
  if (typeof error.detail !== "string") return null;

  const code = DETAIL_CODES.get(error.detail.toLowerCase());
  if (!code) return null;

  return serviceError(code, `HTTP ${error.status}: ${error.detail}`, error);
};
