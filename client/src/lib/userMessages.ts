/**
 * The one place a `ServiceError.code` becomes user-facing copy.
 *
 * Every canonical code of `lib/errors.ts` and every feature code declared in a
 * `<name>.errors.ts` gets a line here: a code with no line silently renders the
 * generic fallback. Technical messages never reach this table — the UI reads
 * `code` and nothing else.
 */
const FALLBACK = "Une erreur est survenue";

const MESSAGES: Record<string, string> = {
  unauthorized: "Session expirée",
  forbidden: "Accès refusé",
  not_found: "Élément introuvable",
  validation_failed: "Certaines informations sont invalides",
  conflict: "Cette donnée existe déjà",
  server_error: "Le service est momentanément indisponible. Réessayez.",
  network_error: "Erreur de connexion",
  timeout: "Le délai d'attente est dépassé.",
  rate_limited: "Trop de tentatives. Patientez un instant avant de réessayer.",
  unknown_error: FALLBACK,
  invalid_credentials: "Email ou mot de passe incorrect",
  invalid_reset_token: "Le lien de réinitialisation est invalide ou expiré",
  invalid_current_password: "Le mot de passe actuel est incorrect",
  email_already_registered: "Cet email est déjà utilisé",
};

/**
 * User-facing message for a `ServiceError` code, in French.
 *
 * Falls back to a generic sentence — a raw code must never reach the screen.
 */
export function userMessageFor(code: string): string {
  return MESSAGES[code] ?? FALLBACK;
}
