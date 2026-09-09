import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiPost, apiPut } from "@/lib/apiClient";
import { HttpError } from "@/lib/errors";
import { ok } from "@/lib/result";
import { changePassword, updateProfile } from "./settings.service";

vi.mock("@/lib/apiClient");

describe("updateProfile", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the profile the transport sent back", async () => {
    const profile = {
      id: "u-1",
      email: "a@b.fr",
      first_name: "Ada",
      last_name: "Lovelace",
      tenant_name: "Cabinet Ada",
      tenant_plan: "pro",
    };
    vi.mocked(apiPut).mockResolvedValue(profile);

    await expect(
      updateProfile({ first_name: "Ada", last_name: "Lovelace" }),
    ).resolves.toEqual(ok(profile));
  });

  it("targets the profile endpoint with the payload it was given", async () => {
    vi.mocked(apiPut).mockResolvedValue({});

    await updateProfile({ first_name: "Ada", last_name: "Lovelace" });

    expect(apiPut).toHaveBeenCalledWith("/auth/me", { first_name: "Ada", last_name: "Lovelace" });
  });

  it("surfaces an HTTP failure as a failed result, not as an empty value", async () => {
    vi.mocked(apiPut).mockRejectedValue(
      new HttpError(422, [
        { type: "missing", loc: ["body", "first_name"], msg: "Field required" },
      ]),
    );

    await expect(
      updateProfile({ first_name: null, last_name: null }),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "validation_failed" },
    });
  });
});

describe("changePassword", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the message the transport sent back", async () => {
    vi.mocked(apiPost).mockResolvedValue({ message: "Mot de passe modifié" });

    await expect(changePassword("old", "new")).resolves.toEqual(
      ok({ message: "Mot de passe modifié" }),
    );
  });

  it("sends both passwords under their snake_case transport names", async () => {
    vi.mocked(apiPost).mockResolvedValue({ message: "ok" });

    await changePassword("old-secret", "new-secret");

    expect(apiPost).toHaveBeenCalledWith("/auth/change-password", {
      current_password: "old-secret",
      new_password: "new-secret",
    });
  });

  it("surfaces a rejected current password under its own code", async () => {
    vi.mocked(apiPost).mockRejectedValue(
      new HttpError(401, "invalid current password"),
    );

    await expect(changePassword("wrong", "new")).resolves.toMatchObject({
      success: false,
      error: { code: "invalid_current_password" },
    });
  });
});
