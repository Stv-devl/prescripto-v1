import { z } from "zod";

/**
 * Shared password validation rules for signup, reset, and change password forms.
 */
/**
 * bcrypt refuses a password past 72 bytes rather than truncating it, so the
 * bound is on UTF-8 bytes, not characters: `.max(72)` would count code units
 * and let a 72-character accented password (up to 144 bytes) through to the
 * server, where bcrypt raises.
 */
const MAX_PASSWORD_BYTES = 72;

export const passwordRules = z
  .string()
  .min(8, "8 caractères minimum")
  .refine(
    (value) => new TextEncoder().encode(value).length <= MAX_PASSWORD_BYTES,
    "72 octets maximum",
  )
  .regex(/[A-Z]/, "Doit contenir au moins une majuscule")
  .regex(/[0-9]/, "Doit contenir au moins un chiffre")
  .regex(/[^A-Za-z0-9]/, "Doit contenir au moins un caractère spécial");
