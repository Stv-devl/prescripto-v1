import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HttpError,
  NetworkError,
  TimeoutError,
  serviceErrorFrom,
  type ServiceErrorCode,
} from "./errors";
import { userMessageFor } from "./userMessages";

function frenchFor(error: unknown): string {
  return userMessageFor(serviceErrorFrom(error).code);
}

describe("the French text a backend response produces", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps « Élément introuvable » on a 404, as today", () => {
    expect(
      frenchFor(
        new HttpError(404, "Project 3f2b1a90-0000-4000-8000-000000000001 not found"),
      ),
    ).toBe("Élément introuvable");
  });

  it("keeps « Erreur de connexion » on a failed upload, as today", () => {
    expect(frenchFor(new NetworkError("Network error during upload"))).toBe(
      "Erreur de connexion",
    );
  });

  it("says « Le délai d'attente est dépassé. » on an expired deadline, not « Erreur de connexion »", () => {
    expect(frenchFor(new TimeoutError("Request timed out"))).toBe(
      "Le délai d'attente est dépassé.",
    );
  });

  it("now says « Erreur de connexion » on a rejected fetch, which used to fall back", () => {
    expect(frenchFor(new NetworkError("Failed to fetch"))).toBe(
      "Erreur de connexion",
    );
  });

  it("now says « Accès refusé » on a 403, which used to fall back", () => {
    expect(frenchFor(new HttpError(403, "Access denied to this project"))).toBe(
      "Accès refusé",
    );
  });

  it("now says « Session expirée » on an expired token, which used to fall back", () => {
    expect(frenchFor(new HttpError(401, "Invalid or expired token"))).toBe(
      "Session expirée",
    );
  });

  it("now says « Certaines informations sont invalides » on a 422, which used to fall back", () => {
    expect(
      frenchFor(
        new HttpError(422, [
          { type: "missing", loc: ["body", "email"], msg: "Field required" },
        ]),
      ),
    ).toBe("Certaines informations sont invalides");
  });

  it("now names the outage on a 500, which used to fall back", () => {
    expect(frenchFor(new HttpError(500, "Internal Server Error"))).toBe(
      "Le service est momentanément indisponible. Réessayez.",
    );
  });
});

describe("the four 404 bodies that carry no « not found »", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("now says « Élément introuvable » when no summary exists", () => {
    expect(
      frenchFor(new HttpError(404, "No summary found for this project")),
    ).toBe("Élément introuvable");
  });

  it("now says « Élément introuvable » on a split position past the text", () => {
    expect(
      frenchFor(new HttpError(404, "Split position exceeds chunk text length")),
    ).toBe("Élément introuvable");
  });

  it("now says « Élément introuvable » on a split producing an empty chunk", () => {
    expect(
      frenchFor(new HttpError(404, "Split would produce an empty chunk")),
    ).toBe("Élément introuvable");
  });

  it("now says « Élément introuvable » on a merge across two documents", () => {
    expect(
      frenchFor(new HttpError(404, "Chunks must belong to the same document")),
    ).toBe("Élément introuvable");
  });
});

describe("userMessageFor", () => {
  it("names a conflict without claiming a concurrent edit nobody made", () => {
    expect(userMessageFor("conflict")).toBe("Cette donnée existe déjà");
  });

  it("falls back to the generic sentence for a code nobody declared", () => {
    expect(userMessageFor("code_that_does_not_exist")).toBe(
      "Une erreur est survenue",
    );
  });

  it("never lets a raw code reach the screen", () => {
    expect(userMessageFor("kerberos_handshake_failed")).not.toContain(
      "kerberos",
    );
  });

  it("tells being too fast apart from being wrong", () => {
    // The worst message a login screen can show is that the password is wrong
    // when it is not.
    expect(userMessageFor("rate_limited")).not.toBe(
      userMessageFor("invalid_credentials"),
    );
    expect(userMessageFor("rate_limited")).toContain("Trop de tentatives");
  });

  it("declares a line for every canonical code", () => {
    const canonical: ServiceErrorCode[] = [
      "unauthorized",
      "forbidden",
      "not_found",
      "validation_failed",
      "conflict",
      "server_error",
      "network_error",
      "timeout",
      "rate_limited",
      "unknown_error",
    ];

    const withoutALine = canonical.filter(
      (code) => userMessageFor(code) === "Une erreur est survenue",
    );

    expect(withoutALine).toEqual(["unknown_error"]);
  });

  it("declares a line for every feature code", () => {
    const featureCodes = [
      "invalid_credentials",
      "invalid_reset_token",
      "invalid_current_password",
      "email_already_registered",
    ];

    const withoutALine = featureCodes.filter(
      (code) => userMessageFor(code) === "Une erreur est survenue",
    );

    expect(withoutALine).toEqual([]);
  });
});
