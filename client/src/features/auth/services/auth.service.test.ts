import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "@/lib/apiClient";
import { HttpError } from "@/lib/errors";
import { ok } from "@/lib/result";
import {
  forgotPassword,
  getMe,
  login,
  refreshTokens,
  resetPassword,
  signup,
} from "./auth.service";

vi.mock("@/lib/apiClient");

const TOKENS = { access_token: "acc", refresh_token: "ref" };

describe("auth.service — token-returning calls", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiPost).mockResolvedValue(TOKENS);
  });

  it("returns the token pair the transport sent back on login", async () => {
    await expect(
      login({ email: "a@b.fr", password: "secret" }),
    ).resolves.toEqual(ok(TOKENS));
    expect(apiPost).toHaveBeenCalledWith("/auth/login", {
      email: "a@b.fr",
      password: "secret",
    });
  });

  it("returns the token pair the transport sent back on signup", async () => {
    await expect(
      signup({ name: "Cabinet Ada", email: "a@b.fr", password: "secret" }),
    ).resolves.toEqual(ok(TOKENS));
    expect(apiPost).toHaveBeenCalledWith("/auth/signup", {
      name: "Cabinet Ada",
      email: "a@b.fr",
      password: "secret",
    });
  });

  it("returns the token pair the transport sent back on refresh", async () => {
    await expect(refreshTokens("ref-1")).resolves.toEqual(ok(TOKENS));
  });

  it("sends the refresh token in the body, not in a header", async () => {
    await refreshTokens("ref-1");

    expect(apiPost).toHaveBeenCalledWith("/auth/refresh", {
      refresh_token: "ref-1",
    });
  });
});

describe("auth.service — message-returning calls", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiPost).mockResolvedValue({ message: "Email envoyé" });
  });

  it("returns the message the transport sent back on forgotPassword", async () => {
    await expect(forgotPassword("a@b.fr")).resolves.toEqual(
      ok({ message: "Email envoyé" }),
    );
    expect(apiPost).toHaveBeenCalledWith("/auth/forgot-password", {
      email: "a@b.fr",
    });
  });

  it("returns the message the transport sent back on resetPassword", async () => {
    await expect(resetPassword("tok", "newpass")).resolves.toEqual(
      ok({ message: "Email envoyé" }),
    );
    expect(apiPost).toHaveBeenCalledWith("/auth/reset-password", {
      token: "tok",
      password: "newpass",
    });
  });
});

describe("auth.service — the authenticated identity", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the user the transport sent back", async () => {
    const user = {
      id: "u-1",
      email: "a@b.fr",
      role: "member",
      tenant_id: "t-1",
      first_name: "Ada",
      last_name: "Lovelace",
      tenant_name: "Cabinet Ada",
      tenant_plan: "pro",
      created_at: "2026-09-01T00:00:00Z",
    };
    vi.mocked(apiGet).mockResolvedValue(user);

    await expect(getMe()).resolves.toEqual(ok(user));
    expect(apiGet).toHaveBeenCalledWith("/auth/me");
  });

  it("surfaces an expired session on getMe as a failed result, not a null user", async () => {
    vi.mocked(apiGet).mockRejectedValue(
      new HttpError(401, "Invalid or expired token"),
    );

    await expect(getMe()).resolves.toMatchObject({
      success: false,
      error: { code: "unauthorized" },
    });
  });
});

describe("auth.service — failures", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("surfaces rejected login credentials under their own code, not empty tokens", async () => {
    vi.mocked(apiPost).mockRejectedValue(
      new HttpError(401, "invalid login credentials"),
    );

    await expect(
      login({ email: "a@b.fr", password: "wrong" }),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "invalid_credentials" },
    });
  });

  it("surfaces an email the backend already knows under its own code", async () => {
    vi.mocked(apiPost).mockRejectedValue(
      new HttpError(409, "email already registered"),
    );

    await expect(
      signup({ name: "Cabinet Ada", email: "a@b.fr", password: "secret" }),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "email_already_registered" },
    });
  });

  it("surfaces an expired reset link under its own code", async () => {
    vi.mocked(apiPost).mockRejectedValue(
      new HttpError(401, "invalid reset token"),
    );

    await expect(resetPassword("stale", "newpass")).resolves.toMatchObject({
      success: false,
      error: { code: "invalid_reset_token" },
    });
  });
});
