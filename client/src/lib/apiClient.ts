import { API_BASE_URL } from "@/config/env";
import { HttpError, NetworkError, TimeoutError } from "@/lib/errors";
import { useAuthStore } from "@/lib/store/authStore";
import {
  beginSessionScope,
  type SessionScope,
} from "@/lib/store/sessionReset";

const BASE_URL = API_BASE_URL;

/**
 * How long a response has to start, and then to be read, in ms.
 *
 * Deliberately loose: the 539 ms measured on the slowest read was on loopback,
 * where the round trip that dominates it does not exist. For any deadline L the
 * worst case is 3L + 30 s — header, refresh, replay, then the body armed once —
 * and reaching it means no deadline fired, so it ends on a status, not on an
 * expiry. React Query still replays that once on a READ (`retry` sits under
 * `queries`; a v5 mutation defaults to `retry: 0`), which doubles it. What no
 * longer doubles is an expiry: it carries `timeout`, which `queryClient.ts`
 * refuses to replay. Rationale: docs/work/apiclient-timeout-long/plan.md.
 */
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * The deadline for a write that legitimately takes tens of seconds, in ms.
 *
 * Two callers, both re-ingestion. Worst case 3 x 120 + 30 = 390 s, undoubled.
 * Nothing may block an interaction for that long. `batch_enrich_keywords` loops
 * over every keyword-less chunk of the PROJECT, so a large one is cut here —
 * a backend shape to fix, not a number to raise.
 */
const SLOW_REQUEST_TIMEOUT_MS = 120_000;

/** Options for a write. `slow` asks for the long deadline. */
export type PostOptions = { slow?: boolean };

let _isRefreshing = false;
let _refreshPromise: Promise<void> | null = null;

function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    h["Authorization"] = `Bearer ${token}`;
  }
  return h;
}

function bearerHeaders(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  const h: Record<string, string> = {};
  if (token) {
    h["Authorization"] = `Bearer ${token}`;
  }
  return h;
}

function isTokenPair(
  value: unknown,
): value is { access_token: string; refresh_token: string } {
  if (typeof value !== "object" || value === null) return false;
  const pair = value as Record<string, unknown>;
  return (
    typeof pair["access_token"] === "string" &&
    typeof pair["refresh_token"] === "string"
  );
}

async function tryRefresh(inSession: SessionScope): Promise<boolean> {
  const store = useAuthStore;
  const refreshToken = store.getState().refreshToken;
  if (!refreshToken) return false;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: ctrl.signal,
    });

    if (!res.ok) return false;

    const data: unknown = await res.json();
    if (!isTokenPair(data)) return false;
    if (!store.getState().isAuthenticated) return false;

    return inSession(() => {
      store.getState().renewTokens(data.access_token, data.refresh_token);
    });
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function handleUnauthorized(): Promise<boolean> {
  if (!useAuthStore.getState().isAuthenticated) return false;

  const inSession = beginSessionScope();
  const stillSameSession = (): boolean =>
    inSession(() => undefined) && useAuthStore.getState().isAuthenticated;

  if (_isRefreshing) {
    await _refreshPromise;
    return stillSameSession();
  }

  _isRefreshing = true;
  _refreshPromise = tryRefresh(inSession).then((refreshed) => {
    _isRefreshing = false;
    _refreshPromise = null;
    inSession(() => {
      if (!refreshed) {
        useAuthStore.getState().logout();
        window.location.href = "/login";
      }
    });
  });

  await _refreshPromise;
  return stillSameSession();
}

type Parsed = { parsed: true; value: unknown } | { parsed: false };

function parseJson(text: string): Parsed {
  try {
    return { parsed: true, value: JSON.parse(text) as unknown };
  } catch {
    return { parsed: false };
  }
}

function detailOf(body: unknown): unknown {
  if (body !== null && typeof body === "object" && "detail" in body) {
    return (body as { detail: unknown }).detail;
  }
  return "Unknown error";
}

async function send(doFetch: () => Promise<Response>): Promise<Response> {
  try {
    return await doFetch();
  } catch (cause) {
    throw new NetworkError(
      cause instanceof Error ? cause.message : "Network request failed",
    );
  }
}

async function readDetail(res: Response): Promise<unknown> {
  const body: unknown = await res.json().catch(() => null);
  return detailOf(body);
}

/**
 * The clock shared by an attempt and the body read that follows it.
 *
 * `once` re-invokes the closure after a refresh, so each attempt gets a fresh
 * controller; the flag says whether one of our own timers fired, which
 * `readDetail` would otherwise hide behind an ordinary HttpError.
 */
function deadline(ms?: number) {
  let expired = false;
  let live: AbortController | undefined;

  const arm = (ctrl: AbortController): ReturnType<typeof setTimeout> | undefined =>
    ms === undefined
      ? undefined
      : setTimeout(() => {
          expired = true;
          ctrl.abort();
        }, ms);

  return {
    attempt:
      (makeFetch: (signal: AbortSignal) => Promise<Response>) =>
      (): Promise<Response> => {
        expired = false;
        const ctrl = new AbortController();
        live = ctrl;
        const timer = arm(ctrl);
        return makeFetch(ctrl.signal).finally(() => clearTimeout(timer));
      },
    armBody: (): ReturnType<typeof setTimeout> | undefined =>
      live === undefined ? undefined : arm(live),
    timedOut: (): boolean => expired,
  };
}

async function once(doFetch: () => Promise<Response>): Promise<Response> {
  const res = await send(doFetch);
  if (res.status !== 401) return res;

  const refreshed = await handleUnauthorized();
  return refreshed ? send(doFetch) : res;
}

/**
 * Runs a request under two deadlines: one for the response to start, one for its
 * body to be read. The first is cleared when the fetch settles, so waiting on a
 * token refresh is not charged to the attempt that triggered it.
 *
 * @param makeFetch - Builds the call; receives the signal of the current attempt.
 * @param ms - Deadline for each phase. `undefined` caps nothing.
 */
async function request<T>(
  makeFetch: (signal: AbortSignal) => Promise<Response>,
  ms?: number,
): Promise<T> {
  const run = deadline(ms);

  let res: Response;
  try {
    res = await once(run.attempt(makeFetch));
  } catch (cause) {
    if (run.timedOut()) throw new TimeoutError("Request timed out");
    throw cause;
  }

  const bodyTimer = run.armBody();
  try {
    if (!res.ok) throw new HttpError(res.status, await readDetail(res));
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (cause) {
    if (run.timedOut()) throw new TimeoutError("Request timed out");
    throw cause;
  } finally {
    clearTimeout(bodyTimer);
  }
}

async function requestVoid(doFetch: () => Promise<Response>): Promise<void> {
  const res = await once(doFetch);
  if (!res.ok) throw new HttpError(res.status, await readDetail(res));
}

function jsonFetch(
  path: string,
  method: string,
  body: unknown,
): (signal: AbortSignal) => Promise<Response> {
  return (signal) =>
    fetch(`${BASE_URL}${path}`, {
      method,
      headers: authHeaders(),
      body: JSON.stringify(body),
      signal,
    });
}

/** GET request to the backend API. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>(
    (signal) => fetch(`${BASE_URL}${path}`, { headers: authHeaders(), signal }),
    REQUEST_TIMEOUT_MS,
  );
}

/**
 * POST request with JSON body.
 *
 * Always passes a deadline, so omitting `opts` means the short one — never the
 * uncapped branch `request` still has for `uploadFile`.
 *
 * @param opts `{ slow: true }` for a re-ingestion call, which needs the long one.
 */
export function apiPost<T>(
  path: string,
  body: unknown,
  opts?: PostOptions,
): Promise<T> {
  return request<T>(
    jsonFetch(path, "POST", body),
    opts?.slow ? SLOW_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS,
  );
}

/** PUT request with JSON body. */
export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(jsonFetch(path, "PUT", body), REQUEST_TIMEOUT_MS);
}

/** PATCH request with JSON body. */
export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(jsonFetch(path, "PATCH", body), REQUEST_TIMEOUT_MS);
}

/**
 * DELETE request. Returns void and reads no body.
 *
 * Deliberately uncapped. `delete_folder` loops over its documents and calls
 * `delete_document`, which commits once per document after dropping its Qdrant
 * points and unlinking its file, with no enclosing transaction. Cutting that
 * loop leaves the first documents permanently gone and the rest intact — a slow
 * call turned into a half-applied one. Capping deletes needs that transaction
 * first. (`delete_project` is a single commit and would be safe; the cap is a
 * property of the verb, not of one route.)
 */
export function apiDelete(path: string): Promise<void> {
  return requestVoid(() =>
    fetch(`${BASE_URL}${path}`, { method: "DELETE", headers: authHeaders() }),
  );
}

/**
 * Upload a file as multipart/form-data.
 *
 * Deliberately uncapped: how long an upload takes depends on the file size and
 * the uplink, so a fixed deadline would cut legitimate transfers.
 */
export function uploadFile<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);

  return request<T>((signal) =>
    fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: bearerHeaders(),
      body: formData,
      signal,
    }),
  );
}

/**
 * Deliberately uncapped, like `uploadFile`: an upload's duration follows the
 * file size and the uplink, so a fixed deadline would cut legitimate transfers.
 */
function sendUpload<T>(
  path: string,
  formData: FormData,
  onProgress: (percent: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      const body = parseJson(xhr.responseText);
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(
          new HttpError(
            xhr.status,
            detailOf(body.parsed ? body.value : null),
          ),
        );
        return;
      }
      if (!body.parsed) {
        reject(
          new HttpError(xhr.status, "Upload succeeded with an unreadable body"),
        );
        return;
      }
      resolve(body.value as T);
    });

    xhr.addEventListener("error", () => {
      reject(new NetworkError("Network error during upload"));
    });

    xhr.open("POST", `${BASE_URL}${path}`);
    const token = useAuthStore.getState().accessToken;
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }
    xhr.send(formData);
  });
}

async function upload<T>(
  path: string,
  formData: FormData,
  onProgress: (percent: number) => void,
): Promise<T> {
  try {
    return await sendUpload<T>(path, formData, onProgress);
  } catch (error) {
    if (error instanceof HttpError && error.status === 401) {
      const refreshed = await handleUnauthorized();
      if (refreshed) return sendUpload<T>(path, formData, onProgress);
    }
    throw error;
  }
}

/**
 * Upload a file with progress tracking via XMLHttpRequest.
 * @param onProgress - Callback receiving upload percentage (0–100).
 */
export function uploadFileWithProgress<T>(
  path: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<T> {
  return uploadFileWithProgressAndFields<T>(path, file, {}, onProgress);
}

/**
 * Upload a file with progress tracking and extra FormData fields.
 * @param extraFields - Additional key/value pairs appended to the FormData.
 * @param onProgress - Callback receiving upload percentage (0–100).
 */
export function uploadFileWithProgressAndFields<T>(
  path: string,
  file: File,
  extraFields: Record<string, string>,
  onProgress: (percent: number) => void,
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  for (const [key, value] of Object.entries(extraFields)) {
    formData.append(key, value);
  }

  return upload<T>(path, formData, onProgress);
}

/** POST request returning a ReadableStream for SSE consumption. */
export function fetchSSE(path: string, body: unknown): Promise<Response> {
  const run = deadline(REQUEST_TIMEOUT_MS);
  return send(
    run.attempt((signal) =>
      fetch(`${BASE_URL}${path}`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(body),
        signal,
      }),
    ),
  ).catch((cause: unknown) => {
    if (run.timedOut()) throw new TimeoutError("Stream did not start in time");
    throw cause;
  });
}
