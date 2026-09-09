import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { serviceError } from "@/lib/errors";
import { err, ok, toServiceError } from "@/lib/result";
import { createQueryClientWrapper } from "@/test/utils";
import * as chatService from "../services/chat.service";
import type { ChatSSEEvent } from "../services/chat.schema";
import type { Message, StreamingMessage } from "../types/types";
import { useChatStream, useDeleteConversation } from "./hooks";

vi.mock("../services/chat.service");

/**
 * Arms `streamChat` with the events it should yield.
 *
 * The service now hands back validated events rather than a raw `Response`:
 * `readSSE` and the Zod schema live below it, and each has its own suite.
 */
function armStream(events: ChatSSEEvent[]): void {
  vi.mocked(chatService.streamChat).mockImplementation(async function* () {
    for (const event of events) yield event;
  });
}

describe("useDeleteConversation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects when the conversation cannot be deleted", async () => {
    vi.mocked(chatService.deleteConversation).mockResolvedValue(
      err(serviceError("not_found", "HTTP 404")),
    );
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDeleteConversation("p-1"), {
      wrapper,
    });

    const caught = await result.current
      .mutateAsync("c-1")
      .catch((error: unknown) => error);

    expect(toServiceError(caught).code).toBe("not_found");
  });

  it("does not invalidate the conversation list when the delete is refused", async () => {
    vi.mocked(chatService.deleteConversation).mockResolvedValue(
      err(serviceError("not_found", "HTTP 404")),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useDeleteConversation("p-1"), {
      wrapper,
    });

    await result.current.mutateAsync("c-1").catch(() => undefined);

    expect(invalidate).not.toHaveBeenCalled();
  });

  it("invalidates the conversation list once the delete succeeds", async () => {
    vi.mocked(chatService.deleteConversation).mockResolvedValue(ok(undefined));
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useDeleteConversation("p-1"), {
      wrapper,
    });

    await result.current.mutateAsync("c-1");

    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["conversations", "p-1"],
    });
  });

  it("resolves when the conversation is deleted", async () => {
    vi.mocked(chatService.deleteConversation).mockResolvedValue(ok(undefined));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useDeleteConversation("p-1"), {
      wrapper,
    });

    await expect(result.current.mutateAsync("c-1")).resolves.toBeUndefined();
  });
});

describe("useChatStream", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("writes the reloaded messages into the cache, not the result wrapper", async () => {
    const messages: Message[] = [
      {
        id: "m-1",
        conversation_id: "c-9",
        role: "user",
        content: "Bonjour",
        sources: [],
        structured: null,
        schema: null,
        created_at: "2026-09-01T00:00:00Z",
      },
    ];
    armStream([{ conversation_id: "c-9" }]);
    vi.mocked(chatService.getMessages).mockResolvedValue(ok(messages));
    const { wrapper, queryClient } = createQueryClientWrapper();
    const { result } = renderHook(() => useChatStream("p-1"), { wrapper });

    await act(async () => {
      await result.current.sendMessage("Bonjour");
    });

    await waitFor(() => {
      expect(queryClient.getQueryData(["messages", "c-9"])).toEqual(messages);
    });
  });
});

describe("useChatStream — what the stream builds", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function stream(events: ChatSSEEvent[]) {
    armStream(events);
    vi.mocked(chatService.getMessages).mockResolvedValue(ok([]));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useChatStream("p-1"), { wrapper });

    await act(async () => {
      await result.current.sendMessage("Quelle épaisseur de dallage ?");
    });

    return result;
  }

  /** The assistant message the stream has been building. */
  function assistant(messages: StreamingMessage[]): StreamingMessage {
    return messages[messages.length - 1];
  }

  it("accumulates the successive text fragments into the assistant message", async () => {
    const result = await stream([{ text: "Le dallage " }, { text: "fait 12 cm" }]);

    expect(assistant(result.current.messages).content).toBe(
      "Le dallage fait 12 cm",
    );
  });

  it("attaches the sources the stream sends to the assistant message", async () => {
    const sources = [
      {
        document_id: "d-1",
        filename: "cctp-lot-03.pdf",
        page: 12,
        lot: "03",
        phase: "PRO",
        text: "Dallage sur terre-plein, épaisseur 12 cm.",
      },
    ];
    const result = await stream([{ text: "Réponse" }, { sources }]);

    expect(assistant(result.current.messages).sources).toEqual(sources);
  });

  it("attaches a structured table and a schema when the stream carries them", async () => {
    const structured = {
      title: "Épaisseurs de dallage",
      columns: ["Ouvrage", "Épaisseur"],
      rows: [{ Ouvrage: "Dallage", Épaisseur: "12 cm" }],
    };
    const schema = {
      schema_type: "multicouche",
      title: "Coupe de dallage",
      params: { epaisseur: "0.12" },
    };
    const result = await stream([{ structured }, { schema }]);

    const last = assistant(result.current.messages);
    expect(last.structured).toEqual(structured);
    expect(last.schema).toEqual(schema);
  });

  it("retains the conversation identifier the first event carries", async () => {
    const result = await stream([{ conversation_id: "c-42" }]);

    expect(result.current.conversationId).toBe("c-42");
  });

  it("tells the user in French when the stream breaks its contract mid-answer", async () => {
    vi.mocked(chatService.streamChat).mockImplementation(
      async function* () {
        yield { text: "Le dallage " };
        throw new Error("event carries none of the keys the chat contract names");
      },
    );
    vi.mocked(chatService.getMessages).mockResolvedValue(ok([]));
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useChatStream("p-1"), { wrapper });

    await act(async () => {
      await result.current.sendMessage("Quelle épaisseur de dallage ?");
    });

    expect(assistant(result.current.messages).content).toContain(
      "Réponse interrompue",
    );
    expect(console.error).toHaveBeenCalledWith(
      "Chat stream error:",
      expect.anything(),
    );
    expect(result.current.isStreaming).toBe(false);
  });

  it("shows the message the stream sends on an error event", async () => {
    const result = await stream([
      { error: "Le service de recherche est temporairement indisponible." },
    ]);

    expect(assistant(result.current.messages).content).toBe(
      "Le service de recherche est temporairement indisponible.",
    );
  });
});
