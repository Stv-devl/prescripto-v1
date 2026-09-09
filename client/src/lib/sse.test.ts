import { describe, expect, it } from "vitest";
import { HttpError } from "./errors";
import { readSSE } from "./sse";

/** A Response whose body streams the given chunks, one enqueue each. */
function streaming(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });

  return new Response(stream, { status: 200 });
}

async function collect(response: Response): Promise<unknown[]> {
  const events: unknown[] = [];
  for await (const event of readSSE(response)) events.push(event);
  return events;
}

describe("readSSE", () => {
  it("yields one parsed payload per data line", async () => {
    const response = streaming([
      'data: {"type":"progress","index":1}\n\n',
      'data: {"type":"progress","index":2}\n\n',
    ]);

    await expect(collect(response)).resolves.toEqual([
      { type: "progress", index: 1 },
      { type: "progress", index: 2 },
    ]);
  });

  it("reassembles an event split across two network chunks", async () => {
    const response = streaming(['data: {"text":"béto', 'n armé"}\n\n']);

    await expect(collect(response)).resolves.toEqual([{ text: "béton armé" }]);
  });

  it("stops at the terminator without yielding it", async () => {
    const response = streaming([
      'data: {"text":"fin"}\n\n',
      "data: [DONE]\n\n",
      'data: {"text":"jamais lu"}\n\n',
    ]);

    await expect(collect(response)).resolves.toEqual([{ text: "fin" }]);
  });

  it("ignores a line that is not a data line", async () => {
    const response = streaming([
      "event: ping\n\n",
      ": keep-alive comment\n\n",
      'data: {"text":"seul"}\n\n',
    ]);

    await expect(collect(response)).resolves.toEqual([{ text: "seul" }]);
  });

  it("skips a malformed payload without ending the stream", async () => {
    const response = streaming([
      "data: {not json\n\n",
      'data: {"text":"après"}\n\n',
    ]);

    await expect(collect(response)).resolves.toEqual([{ text: "après" }]);
  });

  it("throws an HttpError carrying the backend detail on a failed response", async () => {
    const response = new Response(JSON.stringify({ detail: "Project not found" }), {
      status: 404,
    });

    await expect(collect(response)).rejects.toMatchObject({
      name: "HttpError",
      status: 404,
      detail: "Project not found",
    });
  });

  it("throws a NetworkError when the response carries no body", async () => {
    await expect(collect(new Response(null, { status: 200 }))).rejects.toEqual(
      expect.objectContaining({ name: "NetworkError" }),
    );
  });
});

describe("readSSE and the abandoned consumer", () => {
  it("cancels the underlying stream when the consumer stops early", async () => {
    let cancelled = false;
    const encoder = new TextEncoder();
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode('data: {"a":1}\n\ndata: {"b":2}\n\n'));
        },
        cancel() {
          cancelled = true;
        },
      }),
      { status: 200 },
    );

    for await (const event of readSSE(response)) {
      void event;
      break;
    }

    expect(cancelled).toBe(true);
  });

  it("cancels the underlying stream when the consumer throws", async () => {
    let cancelled = false;
    const encoder = new TextEncoder();
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode('data: {"a":1}\n\n'));
        },
        cancel() {
          cancelled = true;
        },
      }),
      { status: 200 },
    );

    await expect(
      (async () => {
        for await (const event of readSSE(response)) {
          void event;
          throw new Error("contract violation");
        }
      })(),
    ).rejects.toThrow("contract violation");

    expect(cancelled).toBe(true);
  });
});

describe("readSSE and the HttpError contract", () => {
  it("reports Unknown error when the failed body carries no detail", async () => {
    const response = new Response(JSON.stringify({ oops: true }), { status: 500 });

    const error = await collect(response).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(HttpError);
    expect((error as HttpError).detail).toBe("Unknown error");
  });
});
