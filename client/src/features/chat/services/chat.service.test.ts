import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiGet, fetchSSE } from "@/lib/apiClient";
import { HttpError } from "@/lib/errors";
import { ok } from "@/lib/result";
import {
  chatStream,
  deleteConversation,
  getMessages,
  listConversations,
} from "./chat.service";

vi.mock("@/lib/apiClient");

describe("chat.service", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the conversation list the transport sent back", async () => {
    const list = {
      conversations: [
        {
          id: "c-1",
          project_id: "p-1",
          user_id: "u-1",
          title: "Lot 3",
          created_at: "2026-09-01T00:00:00Z",
          updated_at: "2026-09-01T00:00:00Z",
        },
      ],
      total: 1,
    };
    vi.mocked(apiGet).mockResolvedValue(list);

    await expect(listConversations("p-1")).resolves.toEqual(ok(list));
    expect(apiGet).toHaveBeenCalledWith("/projects/p-1/conversations");
  });

  it("returns the messages the transport sent back", async () => {
    const messages = [
      {
        id: "m-1",
        conversation_id: "c-1",
        role: "user",
        content: "Bonjour",
        sources: [],
        structured: null,
        schema: null,
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    vi.mocked(apiGet).mockResolvedValue(messages);

    await expect(getMessages("c-1")).resolves.toEqual(ok(messages));
    expect(apiGet).toHaveBeenCalledWith("/conversations/c-1/messages");
  });

  it("resolves without a value when deleting a conversation", async () => {
    vi.mocked(apiDelete).mockResolvedValue(undefined);

    await expect(deleteConversation("c-1")).resolves.toEqual(ok(undefined));
    expect(apiDelete).toHaveBeenCalledWith("/conversations/c-1");
  });

  it("hands back the streaming Response without consuming it", async () => {
    const response = new Response("data: token\n\n");
    vi.mocked(fetchSSE).mockResolvedValue(response);

    const result = await chatStream("p-1", "Quelle épaisseur ?", null);

    expect(result).toBe(response);
    expect(result.bodyUsed).toBe(false);
  });

  it("carries the conversation identifier when the caller supplies one", async () => {
    vi.mocked(fetchSSE).mockResolvedValue(new Response(null));

    await chatStream("p-1", "Suite", "c-9");

    expect(fetchSSE).toHaveBeenCalledWith("/projects/p-1/chat", {
      message: "Suite",
      conversation_id: "c-9",
    });
  });

  it("carries a null conversation identifier, which is what opens a new one", async () => {
    vi.mocked(fetchSSE).mockResolvedValue(new Response(null));

    await chatStream("p-1", "Première question", null);

    expect(fetchSSE).toHaveBeenCalledWith("/projects/p-1/chat", {
      message: "Première question",
      conversation_id: null,
    });
  });

  it("surfaces a server failure on listConversations as a failed result, not an empty list", async () => {
    vi.mocked(apiGet).mockRejectedValue(
      new HttpError(500, "Internal Server Error"),
    );

    await expect(listConversations("p-1")).resolves.toMatchObject({
      success: false,
      error: { code: "server_error" },
    });
  });

  it("surfaces a missing conversation on deleteConversation under its code", async () => {
    vi.mocked(apiDelete).mockRejectedValue(
      new HttpError(404, "Conversation c-1 not found"),
    );

    await expect(deleteConversation("c-1")).resolves.toMatchObject({
      success: false,
      error: { code: "not_found" },
    });
  });

  it("streams the chat events in the order the backend emits them", async () => {
    const { streamChat } = await import("./chat.service");
    const payloads = [
      '{"conversation_id":"c-9"}',
      '{"text":"Le dallage "}',
      '{"text":"fait 12 cm"}',
      "[DONE]",
    ];
    const encoder = new TextEncoder();
    vi.mocked(fetchSSE).mockResolvedValue(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            for (const p of payloads) {
              controller.enqueue(encoder.encode(`data: ${p}\n\n`));
            }
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    const seen = [];
    for await (const event of streamChat("p-1", "Épaisseur ?", null)) {
      seen.push(event);
    }

    expect(seen).toEqual([
      { conversation_id: "c-9" },
      { text: "Le dallage " },
      { text: "fait 12 cm" },
    ]);
  });

  it("ends the stream on the terminator the backend sends", async () => {
    const { streamChat } = await import("./chat.service");
    const payloads = ['{"text":"fin"}', "[DONE]", '{"text":"jamais lu"}'];
    const encoder = new TextEncoder();
    vi.mocked(fetchSSE).mockResolvedValue(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            for (const p of payloads) {
              controller.enqueue(encoder.encode(`data: ${p}\n\n`));
            }
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    const seen = [];
    for await (const event of streamChat("p-1", "Épaisseur ?", null)) {
      seen.push(event);
    }

    expect(seen).toEqual([{ text: "fin" }]);
  });

  it("fails visibly when the stream carries an event outside the contract", async () => {
    const { streamChat } = await import("./chat.service");
    const encoder = new TextEncoder();
    vi.mocked(fetchSSE).mockResolvedValue(
      new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(encoder.encode('data: {"jeton":"x"}\n\n'));
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    await expect(
      (async () => {
        for await (const event of streamChat("p-1", "Épaisseur ?", null)) {
          void event;
        }
      })(),
    ).rejects.toThrow();
  });
});
