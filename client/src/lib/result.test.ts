import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HttpError, serviceError, type ErrorRefiner } from "./errors";
import {
  ServiceFailure,
  attempt,
  err,
  ok,
  toServiceError,
  unwrap,
} from "./result";

describe("unwrap", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the data on a success", () => {
    expect(unwrap(ok(42))).toBe(42);
  });

  it("throws a ServiceFailure carrying the error on a failure", () => {
    const failure = err(serviceError("not_found", "Item missing"));

    let caught: unknown;
    try {
      unwrap(failure);
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ServiceFailure);
    expect(toServiceError(caught).code).toBe("not_found");
  });
});

describe("attempt", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a success carrying the resolved value", async () => {
    await expect(attempt(() => Promise.resolve({ id: "p-1" }))).resolves.toEqual(
      ok({ id: "p-1" }),
    );
  });

  it("returns a failure carrying the code derived from an HttpError", async () => {
    await expect(
      attempt(() => Promise.reject(new HttpError(503, "Service Unavailable"))),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "server_error" },
    });
  });

  it("hands its refiner to the derivation", async () => {
    const refine: ErrorRefiner = () =>
      serviceError("invalid_credentials", "Login rejected");

    await expect(
      attempt(
        () => Promise.reject(new HttpError(401, "invalid login credentials")),
        refine,
      ),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "invalid_credentials" },
    });
  });

  it("lets no exception escape, even when a bare string is thrown", async () => {
    await expect(
      attempt(() => Promise.reject("boom")),
    ).resolves.toMatchObject({
      success: false,
      error: { code: "unknown_error", message: "boom" },
    });
  });
});

describe("toServiceError", () => {
  it("returns the ServiceError carried by a ServiceFailure", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const original = serviceError("conflict", "Already modified");

    expect(toServiceError(new ServiceFailure(original))).toBe(original);

    vi.restoreAllMocks();
  });

  it("passes an already shaped ServiceError through untouched", () => {
    const shaped = { code: "not_found", message: "Item missing" };

    expect(toServiceError(shaped)).toBe(shaped);
  });

  it("falls back to unknown_error on a plain Error", () => {
    expect(toServiceError(new Error("boom"))).toEqual({
      code: "unknown_error",
      message: "boom",
      cause: new Error("boom"),
    });
  });

  it("never logs, because the UI narrows on every render", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    toServiceError(new Error("boom"));
    toServiceError("boom");
    toServiceError({ code: "not_found", message: "gone" });

    expect(spy).not.toHaveBeenCalled();

    vi.restoreAllMocks();
  });
});
