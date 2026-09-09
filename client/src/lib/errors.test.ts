import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HttpError,
  NetworkError,
  TimeoutError,
  formatServiceError,
  isServiceError,
  serviceError,
  serviceErrorFrom,
  type ErrorRefiner,
} from "./errors";

describe("serviceError", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the code, the message and the cause it was given", () => {
    const cause = new Error("underlying");

    expect(serviceError("conflict", "Already modified", cause)).toEqual({
      code: "conflict",
      message: "Already modified",
      cause,
    });
  });

  it("logs the English technical line once", () => {
    const cause = new Error("underlying");

    serviceError("conflict", "Already modified", cause);

    expect(console.error).toHaveBeenCalledTimes(1);
    expect(console.error).toHaveBeenCalledWith(
      "[conflict] Already modified",
      cause,
    );
  });
});

describe("serviceErrorFrom — status to code", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps 401 to unauthorized", () => {
    expect(
      serviceErrorFrom(new HttpError(401, "Invalid or expired token")).code,
    ).toBe("unauthorized");
  });

  it("maps 403 to forbidden", () => {
    expect(
      serviceErrorFrom(new HttpError(403, "Access denied to this project"))
        .code,
    ).toBe("forbidden");
  });

  it("maps 404 to not_found", () => {
    expect(serviceErrorFrom(new HttpError(404, "Chunk not found")).code).toBe(
      "not_found",
    );
  });

  it("maps 409 to conflict", () => {
    expect(
      serviceErrorFrom(new HttpError(409, "email already registered")).code,
    ).toBe("conflict");
  });

  it("maps 429 to rate_limited rather than the unknown fallback", () => {
    // Undeclared, 429 fell through to unknown_error and the screen showed
    // "HTTP 429: too many requests" — English technical text, to a user who had
    // simply gone too fast.
    expect(
      serviceErrorFrom(new HttpError(429, "too many requests")).code,
    ).toBe("rate_limited");
  });

  it("maps 422 to validation_failed", () => {
    expect(
      serviceErrorFrom(new HttpError(422, "File too large: over 10 bytes"))
        .code,
    ).toBe("validation_failed");
  });

  it("maps 400 to validation_failed", () => {
    expect(serviceErrorFrom(new HttpError(400, "Bad Request")).code).toBe(
      "validation_failed",
    );
  });

  it("maps 500 to server_error", () => {
    expect(
      serviceErrorFrom(new HttpError(500, "Internal Server Error")).code,
    ).toBe("server_error");
  });

  it("maps a status nobody declared to unknown_error", () => {
    expect(serviceErrorFrom(new HttpError(418, "I am a teapot")).code).toBe(
      "unknown_error",
    );
  });
});

describe("serviceErrorFrom — business rules", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("reads a 422 whose detail is FastAPI's list, never rendering it as an object", () => {
    const pydanticDetail = [
      { type: "missing", loc: ["body", "email"], msg: "Field required" },
      { type: "missing", loc: ["body", "password"], msg: "Field required" },
    ];

    const error = serviceErrorFrom(new HttpError(422, pydanticDetail));

    expect(error.code).toBe("validation_failed");
    expect(error.message).toBe("HTTP 422: 2 validation error(s)");
  });

  it("says so when the body carries no detail at all", () => {
    const error = serviceErrorFrom(new HttpError(502, null));

    expect(error.code).toBe("server_error");
    expect(error.message).toBe("HTTP 502: no detail");
  });

  it("maps a NetworkError to network_error, apart from any HTTP failure", () => {
    expect(
      serviceErrorFrom(new NetworkError("Network error during upload")).code,
    ).toBe("network_error");
  });

  it("maps a TimeoutError to timeout, not to network_error", () => {
    expect(serviceErrorFrom(new TimeoutError("Request timed out")).code).toBe(
      "timeout",
    );
  });

  it("never lets a TimeoutError fall through to network_error", () => {
    expect(
      serviceErrorFrom(new TimeoutError("Request timed out")).code,
    ).not.toBe("network_error");
  });

  it("keeps a TimeoutError a NetworkError, so the transport branch still holds", () => {
    expect(new TimeoutError("Request timed out")).toBeInstanceOf(NetworkError);
  });

  it("names a TimeoutError for what it is, so a trace does not read as a connection failure", () => {
    expect(new TimeoutError("Request timed out").name).toBe("TimeoutError");
  });

  it("lets a refiner override the code the status would have given", () => {
    const refine: ErrorRefiner = () =>
      serviceError("invalid_credentials", "Login rejected");

    expect(
      serviceErrorFrom(new HttpError(401, "invalid login credentials"), refine)
        .code,
    ).toBe("invalid_credentials");
  });

  it("logs a refined failure only once, so the refiner runs before the status", () => {
    const refine: ErrorRefiner = () =>
      serviceError("invalid_credentials", "Login rejected");

    serviceErrorFrom(new HttpError(401, "invalid login credentials"), refine);

    expect(console.error).toHaveBeenCalledTimes(1);
  });

  it("falls back to the status when the refiner declines", () => {
    const refine: ErrorRefiner = () => null;

    expect(
      serviceErrorFrom(new HttpError(404, "Document not found"), refine).code,
    ).toBe("not_found");
  });

  it("keeps the message in technical English, carrying no user-facing copy", () => {
    const error = serviceErrorFrom(new HttpError(404, "Document not found"));

    expect(error.message).toBe("HTTP 404: Document not found");
  });

  it("stringifies a thrown value that is not an Error", () => {
    const error = serviceErrorFrom("boom");

    expect(error.code).toBe("unknown_error");
    expect(error.message).toBe("boom");
  });

  it("passes an already shaped ServiceError through untouched", () => {
    const shaped = { code: "not_found", message: "Item missing" };

    expect(serviceErrorFrom(shaped)).toBe(shaped);
  });
});

describe("formatServiceError", () => {
  it("renders the code and the technical message on one line", () => {
    expect(
      formatServiceError({ code: "server_error", message: "Insert failed" }),
    ).toBe("[server_error] Insert failed");
  });
});

describe("isServiceError", () => {
  it("accepts an object carrying a code and a message", () => {
    expect(isServiceError({ code: "not_found", message: "gone" })).toBe(true);
  });

  it("rejects null, which is typeof object", () => {
    expect(isServiceError(null)).toBe(false);
  });

  it("rejects a plain Error, which has no code", () => {
    expect(isServiceError(new Error("boom"))).toBe(false);
  });
});
