import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  fetchSSE,
  uploadFile,
  uploadFileWithProgress,
} from "./apiClient";
import { usePendingFolderUploadStore } from "@/features/projects/stores/pendingFolderUploadStore";
import { HttpError, NetworkError, TimeoutError } from "./errors";
import { useAuthStore } from "./store/authStore";

const initialPendingFolderUpload = usePendingFolderUploadStore.getState();

interface XhrStep {
  status: number;
  body: string;
}

let xhrScript: XhrStep[] = [];
let xhrSends: string[] = [];

class FakeXhr {
  status = 0;
  responseText = "";
  readonly upload = {
    addEventListener: (type: string, listener: () => void): void => {
      this.uploadListeners[type] = listener;
    },
  };
  private readonly listeners: Record<string, () => void> = {};
  private readonly uploadListeners: Record<string, () => void> = {};
  private url = "";

  addEventListener(type: string, listener: () => void): void {
    this.listeners[type] = listener;
  }

  open(_method: string, url: string): void {
    this.url = url;
  }

  setRequestHeader(): void {}

  send(): void {
    xhrSends.push(this.url);
    const step = xhrScript.shift();
    queueMicrotask(() => {
      if (!step || step.status === 0) {
        this.listeners["error"]?.();
        return;
      }
      this.status = step.status;
      this.responseText = step.body;
      this.listeners["load"]?.();
    });
  }
}

const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>();

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

function refreshSucceeds(): Response {
  return jsonResponse(200, {
    access_token: "fresh-access",
    refresh_token: "fresh-refresh",
  });
}

function signedIn(): void {
  useAuthStore.setState({
    accessToken: "stale-access",
    refreshToken: "a-refresh-token",
    isAuthenticated: true,
  });
}

function signedOut(): void {
  useAuthStore.setState({
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  Object.defineProperty(window, "location", {
    value: { href: "" },
    writable: true,
    configurable: true,
  });
  fetchMock.mockReset();
  xhrScript = [];
  xhrSends = [];
  signedOut();
  usePendingFolderUploadStore.setState(initialPendingFolderUpload, true);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("a 401 on a screen nobody is signed in to", () => {
  it("does not sign the visitor out and does not redirect", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, { detail: "invalid login credentials" }),
    );

    const failure = await apiPost("/auth/login", {}).catch(
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(HttpError);
    expect(window.location.href).toBe("");
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("does not spend a residual refresh token to resurrect a session", async () => {
    useAuthStore.setState({
      accessToken: null,
      refreshToken: "a-token-left-behind",
      isAuthenticated: false,
    });
    fetchMock.mockResolvedValue(
      jsonResponse(401, { detail: "invalid login credentials" }),
    );

    await apiPost("/auth/login", {}).catch(() => undefined);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("carries the backend detail so the form can display it", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(401, { detail: "invalid login credentials" }),
    );

    const failure = (await apiPost("/auth/login", {}).catch(
      (error: unknown) => error,
    )) as HttpError;

    expect(failure.status).toBe(401);
    expect(failure.detail).toBe("invalid login credentials");
  });
});

describe("the 401 chain on a live session", () => {
  it("replays the request after a successful refresh", async () => {
    signedIn();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(refreshSucceeds())
      .mockResolvedValueOnce(jsonResponse(200, { id: "p-1" }));

    await expect(apiGet("/projects/p-1")).resolves.toEqual({ id: "p-1" });
  });

  it("signs out and redirects when the refresh fails", async () => {
    signedIn();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid token type" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }));

    await apiGet("/projects/p-1").catch(() => undefined);

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(window.location.href).toBe("/login");
  });

  it("clears the feature stores when the refresh fails", async () => {
    signedIn();
    usePendingFolderUploadStore.getState().setPending({
      folderName: "Groupe Vinci — Lot 03",
      files: [new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf")],
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid token type" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }));

    await apiGet("/projects/p-1").catch(() => undefined);

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
  });

  function refreshHeldInFlight(): {
    started: Promise<void>;
    release: (answer: Response) => void;
  } {
    let release: (answer: Response) => void = () => {};
    let markStarted: () => void = () => {};
    const inFlight = new Promise<Response>((resolve) => {
      release = resolve;
    });
    const started = new Promise<void>((resolve) => {
      markStarted = resolve;
    });
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/auth/refresh")) {
        markStarted();
        return inFlight;
      }
      return Promise.resolve(jsonResponse(401, { detail: "Not authenticated" }));
    });
    return { started, release };
  }

  it("never applies a refreshed token pair to a session opened while it was in flight", async () => {
    signedIn();
    const refresh = refreshHeldInFlight();

    const pending = apiGet("/projects/p-1").catch(() => undefined);
    await refresh.started;
    useAuthStore.getState().openSession("access-b", "refresh-b");
    refresh.release(
      jsonResponse(200, {
        access_token: "rotated-access-a",
        refresh_token: "rotated-refresh-a",
      }),
    );
    await pending;

    expect(useAuthStore.getState().accessToken).toBe("access-b");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-b");
  });

  it("never replays the original request under a session opened while the refresh was in flight", async () => {
    signedIn();
    const sent: string[] = [];
    let release: (answer: Response) => void = () => {};
    let markStarted: () => void = () => {};
    const inFlight = new Promise<Response>((resolve) => {
      release = resolve;
    });
    const started = new Promise<void>((resolve) => {
      markStarted = resolve;
    });
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/auth/refresh")) {
        markStarted();
        return inFlight;
      }
      sent.push(url);
      return Promise.resolve(jsonResponse(401, { detail: "Not authenticated" }));
    });

    const pending = apiPost("/projects", { name: "Lot 03" }).catch(
      () => undefined,
    );
    await started;
    useAuthStore.getState().openSession("access-b", "refresh-b");
    release(refreshSucceeds());
    await pending;

    expect(sent).toHaveLength(1);
  });

  it("does not sign out a session opened while a doomed refresh was in flight", async () => {
    signedIn();
    const refresh = refreshHeldInFlight();

    const pending = apiGet("/projects/p-1").catch(() => undefined);
    await refresh.started;
    useAuthStore.getState().openSession("access-b", "refresh-b");
    refresh.release(jsonResponse(401, { detail: "Invalid token type" }));
    await pending;

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().accessToken).toBe("access-b");
    expect(window.location.href).toBe("");
  });

  it("leaves the feature stores alone when the refresh succeeds", async () => {
    signedIn();
    usePendingFolderUploadStore.getState().setPending({
      folderName: "Groupe Vinci — Lot 03",
      files: [new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf")],
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(refreshSucceeds())
      .mockResolvedValueOnce(jsonResponse(200, { id: "p-1" }));

    await apiGet("/projects/p-1").catch(() => undefined);

    expect(usePendingFolderUploadStore.getState().pending?.folderName).toBe(
      "Groupe Vinci — Lot 03",
    );
  });

  it("treats a refresh answered with the wrong shape as a failed refresh", async () => {
    signedIn();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(jsonResponse(200, { detail: "Service moved" }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }));

    await apiGet("/projects").catch(() => undefined);

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("refreshes once for two concurrent unauthorized requests", async () => {
    signedIn();
    const refreshCalls: string[] = [];
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith("/auth/refresh")) {
        refreshCalls.push(url);
        return Promise.resolve(refreshSucceeds());
      }
      if (!url.includes("retried")) {
        return Promise.resolve(
          jsonResponse(401, { detail: "Not authenticated" }),
        );
      }
      return Promise.resolve(jsonResponse(200, { ok: true }));
    });

    await Promise.all([
      apiGet("/projects").catch(() => undefined),
      apiGet("/folders").catch(() => undefined),
    ]);

    expect(refreshCalls).toHaveLength(1);
  });

  it("surfaces a business 401 without a second refresh, a logout or a redirect", async () => {
    signedIn();
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse(401, { detail: "invalid current password" }),
      )
      .mockResolvedValueOnce(refreshSucceeds())
      .mockResolvedValueOnce(
        jsonResponse(401, { detail: "invalid current password" }),
      );

    const failure = (await apiPost("/auth/change-password", {}).catch(
      (error: unknown) => error,
    )) as HttpError;

    expect(failure.detail).toBe("invalid current password");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(window.location.href).toBe("");
  });
});

describe("what the transport throws", () => {
  it("throws an HttpError carrying the status and the raw detail", async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: "Chunk not found" }));

    const failure = (await apiGet("/chunks/c-1").catch(
      (error: unknown) => error,
    )) as HttpError;

    expect(failure.status).toBe(404);
    expect(failure.detail).toBe("Chunk not found");
  });

  it("keeps a validation detail as the list FastAPI sent, not as a string", async () => {
    const pydanticDetail = [
      { type: "missing", loc: ["body", "email"], msg: "Field required" },
    ];
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: pydanticDetail }));

    const failure = (await apiPost("/auth/signup", {}).catch(
      (error: unknown) => error,
    )) as HttpError;

    expect(failure.detail).toEqual(pydanticDetail);
  });

  it("throws a NetworkError when the request never reached the server", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    const failure = await apiGet("/projects").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(NetworkError);
    expect(failure).not.toBeInstanceOf(TimeoutError);
  });

  it("sends a delete through the same refresh chain as the other verbs", async () => {
    signedIn();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(refreshSucceeds())
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(apiDelete("/documents/d-1")).resolves.toBeUndefined();
  });

  it("reads no body on a 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(apiGet("/projects/p-1")).resolves.toBeUndefined();
  });
});

describe("the upload path", () => {
  it("refreshes and replays when the upload is refused with a 401", async () => {
    signedIn();
    xhrScript = [
      { status: 401, body: JSON.stringify({ detail: "Not authenticated" }) },
      { status: 200, body: JSON.stringify({ id: "d-1" }) },
    ];
    fetchMock.mockResolvedValue(refreshSucceeds());

    await expect(
      uploadFileWithProgress("/projects/p-1/documents", new File([], "a.pdf"), () => {}),
    ).resolves.toEqual({ id: "d-1" });
    expect(xhrSends).toHaveLength(2);
  });

  it("does not choke on a failure body that is not JSON", async () => {
    xhrScript = [{ status: 502, body: "<html>Bad Gateway</html>" }];

    const failure = (await uploadFileWithProgress(
      "/projects/p-1/documents",
      new File([], "a.pdf"),
      () => {},
    ).catch((error: unknown) => error)) as HttpError;

    expect(failure).toBeInstanceOf(HttpError);
    expect(failure.status).toBe(502);
  });

  it("refuses a success whose body cannot be read, rather than resolving null", async () => {
    xhrScript = [{ status: 201, body: "<html>Gateway interstitial</html>" }];

    const failure = await uploadFileWithProgress(
      "/projects/p-1/documents",
      new File([], "a.pdf"),
      () => {},
    ).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(HttpError);
  });

  it("reports a transport failure as a NetworkError", async () => {
    xhrScript = [{ status: 0, body: "" }];

    const failure = await uploadFileWithProgress(
      "/projects/p-1/documents",
      new File([], "a.pdf"),
      () => {},
    ).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(NetworkError);
  });
});

describe("a request that never answers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  /** A response whose body honours the signal, like the real one does. */
  function hangingBody(
    signal: AbortSignal | undefined,
    status = 200,
  ): Response {
    return {
      ok: status < 400,
      status,
      json: () =>
        new Promise((_resolve, reject) => {
          signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    } as unknown as Response;
  }

  /** A response whose stream stays open, and errors if the signal aborts. */
  function openStream(signal: AbortSignal | undefined, afterMs: number): Response {
    return {
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          signal?.addEventListener("abort", () =>
            controller.error(new DOMException("aborted", "AbortError")),
          );
          setTimeout(
            () => controller.enqueue(new TextEncoder().encode("data: hi\n\n")),
            afterMs,
          );
        },
      }),
    } as unknown as Response;
  }

  /** A fetch result that refuses a signal already aborted when it is called. */
  function answering(
    signal: AbortSignal | undefined,
    res: Response,
  ): Promise<Response> {
    return signal?.aborted
      ? Promise.reject(new DOMException("aborted", "AbortError"))
      : Promise.resolve(res);
  }

  /** A fetch that answers after `afterMs`, and honours an abort before that. */
  function answersAfter(afterMs: number, body: unknown = { ok: true }): void {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
          setTimeout(() => resolve(jsonResponse(200, body)), afterMs);
        }),
    );
  }

  /** A fetch that never settles unless its signal aborts. */
  function neverAnswers(): void {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
  }

  it("frees the refresh lock when the refresh body never finishes", async () => {
    signedIn();
    fetchMock.mockImplementation((url, init) =>
      url.endsWith("/auth/refresh")
        ? Promise.resolve(hangingBody(init?.signal ?? undefined))
        : Promise.resolve(jsonResponse(401, { detail: "expired" })),
    );

    const first = apiGet("/projects").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(60_000);
    await first;

    const second = apiGet("/projects/p-1").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(60_000);

    expect(await second).toBeInstanceOf(Error);
  });

  it("rejects a read whose answer never arrives", async () => {
    neverAnswers();

    const failure = apiGet("/projects").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("does not cap a delete, whose cascade is not atomic on the backend", async () => {
    let settled = false;
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
          setTimeout(() => resolve(jsonResponse(200, {})), 120_000);
        }),
    );

    const removal = apiDelete("/folders/f-1")
      .catch((error: unknown) => error)
      .finally(() => {
        settled = true;
      });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(61_000);
    await expect(removal).resolves.toBeUndefined();
  });

  it("leaves a read that answers within the deadline untouched", async () => {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
          setTimeout(() => resolve(jsonResponse(200, { id: "p-1" })), 25_000);
        }),
    );

    const read = apiGet("/projects/p-1");
    await vi.advanceTimersByTimeAsync(26_000);

    await expect(read).resolves.toEqual({ id: "p-1" });
  });

  it("rejects a read whose body never finishes, not only one whose headers never arrive", async () => {
    fetchMock.mockImplementation((_url, init) =>
      Promise.resolve(hangingBody(init?.signal ?? undefined)),
    );

    const failure = apiGet("/projects").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("gives the body its own deadline, so slow headers do not consume it", async () => {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve) => {
          setTimeout(() => resolve(hangingBody(init?.signal ?? undefined)), 29_000);
        }),
    );

    let settled = false;
    const failure = apiGet("/projects")
      .catch((error: unknown) => error)
      .finally(() => {
        settled = true;
      });

    await vi.advanceTimersByTimeAsync(32_000);
    expect(settled).toBe(false); // a single timer would already have cut it

    await vi.advanceTimersByTimeAsync(29_000);
    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("reports a failed refresh as an auth error, not as a timeout", async () => {
    signedIn();
    let releaseRefresh: (() => void) | undefined;
    fetchMock.mockImplementation((url) =>
      url.endsWith("/auth/refresh")
        ? new Promise<Response>((resolve) => {
            releaseRefresh = () => resolve(jsonResponse(401, { detail: "nope" }));
          })
        : Promise.resolve(jsonResponse(401, { detail: "expired" })),
    );

    const failure = apiGet("/projects").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(35_000); // past the deadline
    releaseRefresh?.();

    expect(await failure).toBeInstanceOf(HttpError);
  });

  it("lets a stream run far longer than the deadline once it has started", async () => {
    fetchMock.mockImplementation((_url, init) =>
      Promise.resolve(openStream(init?.signal ?? undefined, 90_000)),
    );

    const res = await fetchSSE("/projects/p-1/chat", { message: "bonjour" });
    const chunk = res.body?.getReader().read();
    await vi.advanceTimersByTimeAsync(120_000);

    expect(new TextDecoder().decode((await chunk)?.value)).toBe("data: hi\n\n");
  });

  it("rejects a stream that never starts", async () => {
    neverAnswers();

    const failure = fetchSSE("/projects/p-1/chat", {}).catch(
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("leaves no timer behind, on either outcome", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    const before = vi.getTimerCount();

    await apiGet("/projects");
    await fetchSSE("/projects/p-1/chat", {});

    expect(vi.getTimerCount()).toBe(before);
  });

  it("does not cap an upload, whose duration follows the file and the uplink", async () => {
    let settled = false;
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
          setTimeout(() => resolve(jsonResponse(200, { id: "d-1" })), 120_000);
        }),
    );

    const upload = uploadFile("/projects/p-1/documents", new File([], "a.pdf"))
      .catch((error: unknown) => error)
      .finally(() => {
        settled = true;
      });

    await vi.advanceTimersByTimeAsync(60_000);
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(61_000);
    await expect(upload).resolves.toEqual({ id: "d-1" });
  });

  it("rejects a POST asked without options, whose answer never arrives", async () => {
    neverAnswers();

    const failure = apiPost("/projects", { name: "a" }).catch(
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("leaves a POST that answers within the deadline untouched", async () => {
    answersAfter(25_000, { id: "p-1" });

    const post = apiPost("/projects", { name: "a" });
    await vi.advanceTimersByTimeAsync(26_000);

    await expect(post).resolves.toEqual({ id: "p-1" });
  });

  it("rejects a PUT whose answer never arrives", async () => {
    neverAnswers();

    const failure = apiPut("/me", { first_name: "a" }).catch(
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("rejects a PATCH whose answer never arrives", async () => {
    neverAnswers();

    const failure = apiPatch("/projects/p-1", { name: "b" }).catch(
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("lets a slow POST run past the short deadline, and answer", async () => {
    let settled = false;
    answersAfter(60_000, { chunks: 12 });

    const post = apiPost(
      "/admin/projects/p-1/documents/d-1/rechunk",
      {},
      { slow: true },
    ).finally(() => {
      settled = true;
    });

    await vi.advanceTimersByTimeAsync(31_000);
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(30_000);
    await expect(post).resolves.toEqual({ chunks: 12 });
  });

  it("still cuts a slow POST, at the long deadline", async () => {
    neverAnswers();

    const failure = apiPost(
      "/admin/projects/p-1/documents/d-1/rechunk",
      {},
      { slow: true },
    ).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(121_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("gives a slow POST's body the long deadline too, not the short one", async () => {
    let settled = false;
    fetchMock.mockImplementation((_url, init) =>
      Promise.resolve(hangingBody(init?.signal ?? undefined)),
    );

    const post = apiPost(
      "/admin/projects/p-1/chunks/batch-enrich-keywords",
      {},
      { slow: true },
    )
      .catch((error: unknown) => error)
      .finally(() => {
        settled = true;
      });

    await vi.advanceTimersByTimeAsync(31_000);
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(90_000);
    expect(await post).toBeInstanceOf(TimeoutError);
  });

  it("gives the replay of a slow POST after a 401 its own long deadline", async () => {
    signedIn();
    let call = 0;
    fetchMock.mockImplementation((url, init) => {
      if (url.endsWith("/auth/refresh")) return Promise.resolve(refreshSucceeds());
      call += 1;
      if (call === 1) return Promise.resolve(jsonResponse(401, { detail: "expired" }));
      return new Promise<Response>((resolve, reject) => {
        init?.signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
        setTimeout(() => resolve(jsonResponse(200, { chunks: 3 })), 60_000);
      });
    });

    const post = apiPost(
      "/admin/projects/p-1/documents/d-1/rechunk",
      {},
      { slow: true },
    );
    await vi.advanceTimersByTimeAsync(61_000);

    await expect(post).resolves.toEqual({ chunks: 3 });
  });

  it("reports a slow POST's failed replay for its own failure, not as a timeout", async () => {
    signedIn();
    let call = 0;
    fetchMock.mockImplementation((url) => {
      if (url.endsWith("/auth/refresh")) return Promise.resolve(refreshSucceeds());
      call += 1;
      // Ignores its signal on purpose: the deadline fires, the answer lands anyway.
      return call === 1
        ? new Promise<Response>((resolve) => {
            setTimeout(() => resolve(jsonResponse(401, { detail: "expired" })), 121_000);
          })
        : Promise.resolve(jsonResponse(409, { detail: "conflict" }));
    });

    const pending = apiPost(
      "/admin/projects/p-1/documents/d-1/rechunk",
      {},
      { slow: true },
    ).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(121_000);
    const failure = await pending;

    expect(failure).toBeInstanceOf(HttpError);
    expect((failure as HttpError).status).toBe(409);
  });
  it("reports a body that hangs behind a failing status as a timeout, not as the status", async () => {
    fetchMock.mockImplementation((_url, init) =>
      Promise.resolve(hangingBody(init?.signal ?? undefined, 500)),
    );

    const failure = apiGet("/projects").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });

  it("gives the replay after a slow refresh its own deadline, and it succeeds", async () => {
    signedIn();
    let releaseRefresh: (() => void) | undefined;
    let call = 0;
    fetchMock.mockImplementation((url, init) => {
      if (url.endsWith("/auth/refresh")) {
        return new Promise<Response>((resolve) => {
          releaseRefresh = () =>
            resolve(
              jsonResponse(200, { access_token: "new", refresh_token: "new" }),
            );
        });
      }
      call += 1;
      return call === 1
        ? Promise.resolve(jsonResponse(401, { detail: "expired" }))
        : answering(init?.signal ?? undefined, jsonResponse(200, { id: "p-1" }));
    });

    const read = apiGet("/projects/p-1");
    await vi.advanceTimersByTimeAsync(35_000); // longer than one deadline
    releaseRefresh?.();

    await expect(read).resolves.toEqual({ id: "p-1" });
  });

  it("reports a replay that fails in turn for its own failure, not as a timeout", async () => {
    signedIn();
    let call = 0;
    fetchMock.mockImplementation((url) => {
      if (url.endsWith("/auth/refresh")) {
        return Promise.resolve(
          jsonResponse(200, { access_token: "new", refresh_token: "new" }),
        );
      }
      call += 1;
      // Ignores its signal on purpose: the deadline fires, the answer lands anyway.
      return call === 1
        ? new Promise<Response>((resolve) => {
            setTimeout(
              () => resolve(jsonResponse(401, { detail: "expired" })),
              31_000,
            );
          })
        : Promise.resolve(jsonResponse(409, { detail: "conflict" }));
    });

    const pending = apiGet("/projects/p-1").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(31_000);
    const failure = await pending;

    expect(failure).toBeInstanceOf(HttpError);
    expect((failure as HttpError).status).toBe(409);
  });

  it("leaves no timer behind when a stream fails to start", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const before = vi.getTimerCount();

    const failure = await fetchSSE("/projects/p-1/chat", {}).catch(
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(NetworkError);
    expect(failure).not.toBeInstanceOf(TimeoutError);
    expect(vi.getTimerCount()).toBe(before);
  });

  it("leaves no timer behind when a read fails outright", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const before = vi.getTimerCount();

    const failure = await apiGet("/projects").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(NetworkError);
    expect(vi.getTimerCount()).toBe(before);
  });

  it("leaves no timer behind when the answer is a failing status", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { detail: "boom" }));
    const before = vi.getTimerCount();

    const failure = await apiGet("/projects").catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(HttpError);
    expect(vi.getTimerCount()).toBe(before);
  });

  it("leaves no timer behind after a refresh", async () => {
    signedIn();
    let call = 0;
    fetchMock.mockImplementation((url) => {
      if (url.endsWith("/auth/refresh")) {
        return Promise.resolve(refreshSucceeds());
      }
      call += 1;
      return Promise.resolve(
        call === 1
          ? jsonResponse(401, { detail: "expired" })
          : jsonResponse(200, { id: "p-1" }),
      );
    });
    await apiGet("/projects/p-1");
    // Flushes the store's persist writes, which are timers too. An abort timer
    // is armed for 30 s, so it survives this and stays countable.
    await vi.advanceTimersByTimeAsync(1);

    expect(vi.getTimerCount()).toBe(0);
  });

  it("leaves no timer behind when the refresh is refused", async () => {
    signedIn();
    fetchMock.mockImplementation((url) =>
      Promise.resolve(
        url.endsWith("/auth/refresh")
          ? jsonResponse(401, { detail: "nope" })
          : jsonResponse(401, { detail: "expired" }),
      ),
    );

    await apiGet("/projects").catch(() => undefined);
    await vi.advanceTimersByTimeAsync(1);

    expect(vi.getTimerCount()).toBe(0);
  });

  it("arms the body deadline on the attempt that answered, not on the one it replaced", async () => {
    signedIn();
    let call = 0;
    fetchMock.mockImplementation((url, init) => {
      if (url.endsWith("/auth/refresh")) {
        return Promise.resolve(refreshSucceeds());
      }
      call += 1;
      return Promise.resolve(
        call === 1
          ? jsonResponse(401, { detail: "expired" })
          : hangingBody(init?.signal ?? undefined),
      );
    });

    const failure = apiGet("/projects/p-1").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(31_000);

    expect(await failure).toBeInstanceOf(TimeoutError);
  });
});
