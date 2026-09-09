import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback, useRef } from "react";
import { unwrap } from "@/lib/result";
import {
  listConversations,
  getMessages,
  streamChat,
  deleteConversation,
} from "../services/chat.service";
import type { StreamingMessage } from "../types/types";

/** Replaces the trailing assistant message, leaving the list alone otherwise. */
function amendAssistant(
  messages: StreamingMessage[],
  amend: (last: StreamingMessage) => StreamingMessage,
): StreamingMessage[] {
  const last = messages[messages.length - 1];
  if (last?.role !== "assistant") return messages;

  const updated = [...messages];
  updated[updated.length - 1] = amend(last);
  return updated;
}

/**
 * Fetches conversations for a project.
 */
export function useConversations(projectId: string) {
  return useQuery({
    queryKey: ["conversations", projectId],
    queryFn: async () => unwrap(await listConversations(projectId)),
    enabled: !!projectId,
  });
}

/**
 * Fetches messages for a conversation.
 */
export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: ["messages", conversationId],
    queryFn: async () => unwrap(await getMessages(conversationId!)),
    enabled: !!conversationId,
  });
}

interface ChatStreamState {
  messages: StreamingMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  sendMessage: (
    text: string,
    existingConversationId?: string | null,
  ) => Promise<void>;
  reset: () => void;
}

/**
 * Manages SSE chat streaming for a project.
 * Accumulates tokens into the last assistant message during streaming.
 * After stream completes, clears local messages and invalidates server cache
 * so ChatPanel shows only persisted history (no duplicates).
 */
export function useChatStream(projectId: string): ChatStreamState {
  const [messages, setMessages] = useState<StreamingMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const convIdRef = useRef<string | null>(null);
  const queryClient = useQueryClient();

  const reset = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    convIdRef.current = null;
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (text: string, existingConversationId?: string | null) => {
      const convId = existingConversationId ?? convIdRef.current;

      const userMsg: StreamingMessage = {
        role: "user",
        content: text,
        sources: [],
        structured: null,
        schema: null,
      };
      const assistantMsg: StreamingMessage = {
        role: "assistant",
        content: "",
        sources: [],
        structured: null,
        schema: null,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      try {
        for await (const event of streamChat(projectId, text, convId)) {
          if (event.conversation_id !== undefined) {
            convIdRef.current = event.conversation_id;
            setConversationId(event.conversation_id);
          }

          if (event.text !== undefined) {
            const fragment = event.text;
            setMessages((prev) => amendAssistant(prev, (last) => ({
              ...last,
              content: last.content + fragment,
            })));
          }

          if (event.structured !== undefined) {
            const structured = event.structured;
            setMessages((prev) => amendAssistant(prev, (last) => ({ ...last, structured })));
          }

          if (event.schema !== undefined) {
            const schema = event.schema;
            setMessages((prev) => amendAssistant(prev, (last) => ({ ...last, schema })));
          }

          if (event.sources !== undefined) {
            const sources = event.sources;
            setMessages((prev) => amendAssistant(prev, (last) => ({ ...last, sources })));
          }

          if (event.error !== undefined) {
            const content = event.error;
            setMessages((prev) => amendAssistant(prev, (last) => ({ ...last, content })));
          }
        }
      } catch (err) {
        console.error("Chat stream error:", err);
        setMessages((prev) =>
          amendAssistant(prev, (last) => ({
            ...last,
            content: last.content
              ? `${last.content}\n\n**Réponse interrompue : erreur lors de la génération.**`
              : "Erreur lors de la génération de la réponse.",
          })),
        );
      } finally {
        setIsStreaming(false);
        queryClient.invalidateQueries({
          queryKey: ["conversations", projectId],
        });
        if (convIdRef.current) {
          await queryClient.fetchQuery({
            queryKey: ["messages", convIdRef.current],
            queryFn: async () => unwrap(await getMessages(convIdRef.current!)),
          });
        }
      }
    },
    [projectId, queryClient],
  );

  return { messages, isStreaming, conversationId, sendMessage, reset };
}

/**
 * Deletes a conversation and invalidates the conversations list.
 */
export function useDeleteConversation(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (conversationId: string) =>
      unwrap(await deleteConversation(conversationId)),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["conversations", projectId],
      });
    },
  });
}
