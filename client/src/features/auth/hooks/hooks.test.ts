import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { serviceError } from "@/lib/errors";
import { err, ok, toServiceError } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import * as authService from "../services/auth.service";
import { useForgotPassword, useLogin, useResetPassword } from "./hooks";

vi.mock("../services/auth.service");

describe("useLogin", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("carries the code so the page can pick its French text", async () => {
    vi.mocked(authService.login).mockResolvedValue(
      err(serviceError("invalid_credentials", "HTTP 401")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useLogin(), { wrapper });

    const caught = await result.current
      .mutateAsync({ email: "a@b.fr", password: "wrong" })
      .catch((error: unknown) => error);

    expect(toServiceError(caught).code).toBe("invalid_credentials");
  });

  it("hands the token pair to its caller on success", async () => {
    vi.mocked(authService.login).mockResolvedValue(
      ok({ access_token: "acc", refresh_token: "ref", token_type: "bearer" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useLogin(), { wrapper });

    await expect(
      result.current.mutateAsync({ email: "a@b.fr", password: "secret" }),
    ).resolves.toEqual({
      access_token: "acc",
      refresh_token: "ref",
      token_type: "bearer",
    });
  });
});

describe("useResetPassword", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects on a stale link, so the page never shows its success screen", async () => {
    vi.mocked(authService.resetPassword).mockResolvedValue(
      err(serviceError("invalid_reset_token", "HTTP 401")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useResetPassword(), { wrapper });

    const outcome = await result.current
      .mutateAsync({
        token: "stale",
        data: { password: "new-secret", confirmPassword: "new-secret" },
      })
      .then(() => "resolved")
      .catch(() => "rejected");

    expect(outcome).toBe("rejected");
  });
});

describe("useForgotPassword", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects when the request is refused, so the page keeps its form", async () => {
    vi.mocked(authService.forgotPassword).mockResolvedValue(
      err(serviceError("server_error", "HTTP 500")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useForgotPassword(), { wrapper });

    const caught = await result.current
      .mutateAsync({ email: "a@b.fr" })
      .catch((error: unknown) => error);

    expect(toServiceError(caught).code).toBe("server_error");
  });
});
