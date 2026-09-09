import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpError, serviceErrorFrom } from "@/lib/errors";
import { userMessageFor } from "@/lib/userMessages";
import { refineAuthError } from "./auth.errors";

describe("refineAuthError", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("names rejected login credentials", () => {
    const refined = refineAuthError(
      new HttpError(401, "invalid login credentials"),
    );

    expect(refined?.code).toBe("invalid_credentials");
  });

  it("names an invalid reset token", () => {
    const refined = refineAuthError(new HttpError(401, "invalid reset token"));

    expect(refined?.code).toBe("invalid_reset_token");
  });

  it("names an email the backend already knows", () => {
    const refined = refineAuthError(
      new HttpError(409, "email already registered"),
    );

    expect(refined?.code).toBe("email_already_registered");
  });

  it("recognises a detail whatever its casing", () => {
    const refined = refineAuthError(
      new HttpError(401, "Invalid Login Credentials"),
    );

    expect(refined?.code).toBe("invalid_credentials");
  });

  it("declines a detail nobody declared, so the status decides", () => {
    expect(
      refineAuthError(new HttpError(401, "Invalid or expired token")),
    ).toBeNull();
  });

  it("declines a detail that merely contains a phrase it knows", () => {
    expect(
      refineAuthError(
        new HttpError(401, "Request failed: invalid login credentials (401)"),
      ),
    ).toBeNull();
  });

  it("declines a detail that is not a string", () => {
    expect(refineAuthError(new HttpError(422, [{ msg: "x" }]))).toBeNull();
  });
});

describe("the French text an auth failure still produces", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("still says « Email ou mot de passe incorrect »", () => {
    const error = serviceErrorFrom(
      new HttpError(401, "invalid login credentials"),
      refineAuthError,
    );

    expect(userMessageFor(error.code)).toBe("Email ou mot de passe incorrect");
  });

  it("still says « Le lien de réinitialisation est invalide ou expiré »", () => {
    const error = serviceErrorFrom(
      new HttpError(401, "invalid reset token"),
      refineAuthError,
    );

    expect(userMessageFor(error.code)).toBe(
      "Le lien de réinitialisation est invalide ou expiré",
    );
  });

  it("still says « Cet email est déjà utilisé »", () => {
    const error = serviceErrorFrom(
      new HttpError(409, "email already registered"),
      refineAuthError,
    );

    expect(userMessageFor(error.code)).toBe("Cet email est déjà utilisé");
  });
});
