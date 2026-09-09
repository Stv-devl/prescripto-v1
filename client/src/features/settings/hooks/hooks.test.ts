import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { serviceError } from "@/lib/errors";
import { err, ok, toServiceError } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { createQueryClientWrapper, createTestQueryClient } from "@/test/utils";
import type { User } from "@/types/user";
import * as settingsService from "../services/settings.service";
import { useUpdateProfile } from "./hooks";
import { useChangePassword } from "./useChangePassword";

vi.mock("../services/settings.service");

const initialAuth = useAuthStore.getState();

const aUser: User = {
  id: "user-a",
  email: "economiste@vinci.fr",
  role: "member",
  tenant_id: "tenant-a",
  first_name: "Camille",
  last_name: "Roux",
  tenant_name: "Groupe Vinci",
  tenant_plan: "pro",
  created_at: "2026-01-15T09:00:00Z",
};

describe("useChangePassword", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects when the service refuses the current password", async () => {
    vi.mocked(settingsService.changePassword).mockResolvedValue(
      err(serviceError("invalid_current_password", "HTTP 401")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useChangePassword(), { wrapper });

    const outcome = await result.current
      .mutateAsync({ currentPassword: "wrong", newPassword: "new-secret" })
      .then(() => "resolved")
      .catch(() => "rejected");

    expect(outcome).toBe("rejected");
  });

  it("carries the code, so the modal can pick its French text", async () => {
    vi.mocked(settingsService.changePassword).mockResolvedValue(
      err(serviceError("invalid_current_password", "HTTP 401")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useChangePassword(), { wrapper });

    const caught = await result.current
      .mutateAsync({ currentPassword: "wrong", newPassword: "new-secret" })
      .catch((error: unknown) => error);

    expect(toServiceError(caught).code).toBe("invalid_current_password");
  });

  it("resolves with the message on a successful change", async () => {
    vi.mocked(settingsService.changePassword).mockResolvedValue(
      ok({ message: "Mot de passe modifié" }),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useChangePassword(), { wrapper });

    await expect(
      result.current.mutateAsync({
        currentPassword: "old-secret",
        newPassword: "new-secret",
      }),
    ).resolves.toEqual({ message: "Mot de passe modifié" });
  });
});

describe("useUpdateProfile", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
    useAuthStore.setState(initialAuth, true);
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reaches its error state when the update is refused", async () => {
    vi.mocked(settingsService.updateProfile).mockResolvedValue(
      err(serviceError("validation_failed", "HTTP 422")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useUpdateProfile(), { wrapper });

    result.current.mutate({ first_name: null, last_name: null });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
    expect(toServiceError(result.current.error).code).toBe("validation_failed");
  });

  it("puts the profile back when the update is refused inside the same session", async () => {
    vi.mocked(settingsService.updateProfile).mockResolvedValue(
      err(serviceError("validation_failed", "HTTP 422")),
    );
    const { wrapper, queryClient } = createQueryClientWrapper(
      createTestQueryClient(Infinity),
    );
    queryClient.setQueryData(["auth", "me"], aUser);
    const { result } = renderHook(() => useUpdateProfile(), { wrapper });

    result.current.mutate({ first_name: "Camille", last_name: "Roux" });
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(queryClient.getQueryData(["auth", "me"])).toEqual(aUser);
  });

  it("does not put the previous tenant's profile back after a session boundary", async () => {
    let refuse: (result: Awaited<ReturnType<typeof settingsService.updateProfile>>) => void =
      () => {};
    const refused = new Promise<
      Awaited<ReturnType<typeof settingsService.updateProfile>>
    >((resolve) => {
      refuse = resolve;
    });
    vi.mocked(settingsService.updateProfile).mockReturnValue(refused);
    const { wrapper, queryClient } = createQueryClientWrapper(
      createTestQueryClient(Infinity),
    );
    queryClient.setQueryData(["auth", "me"], aUser);
    const { result } = renderHook(() => useUpdateProfile(), { wrapper });

    result.current.mutate({ first_name: "Camille", last_name: "Roux" });
    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });
    queryClient.clear();
    useAuthStore.getState().openSession("access-b", "refresh-b");
    refuse(err(serviceError("validation_failed", "HTTP 422")));
    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(queryClient.getQueryData(["auth", "me"])).toBeUndefined();
  });
});
