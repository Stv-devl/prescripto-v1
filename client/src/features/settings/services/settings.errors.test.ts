import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpError, serviceErrorFrom } from "@/lib/errors";
import { userMessageFor } from "@/lib/userMessages";
import { refineSettingsError } from "./settings.errors";

describe("refineSettingsError", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("names the rejected current password", () => {
    const refined = refineSettingsError(
      new HttpError(401, "invalid current password"),
    );

    expect(refined?.code).toBe("invalid_current_password");
  });

  it("recognises the detail whatever its casing", () => {
    const refined = refineSettingsError(
      new HttpError(401, "Invalid Current Password"),
    );

    expect(refined?.code).toBe("invalid_current_password");
  });

  it("declines a detail nobody declared, so the status decides", () => {
    expect(refineSettingsError(new HttpError(404, "User not found"))).toBeNull();
  });

  it("declines a detail that is not a string", () => {
    expect(refineSettingsError(new HttpError(422, [{ msg: "x" }]))).toBeNull();
  });

  it("still shows « Le mot de passe actuel est incorrect » end to end", () => {
    const error = serviceErrorFrom(
      new HttpError(401, "invalid current password"),
      refineSettingsError,
    );

    expect(userMessageFor(error.code)).toBe(
      "Le mot de passe actuel est incorrect",
    );
  });
});
