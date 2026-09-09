import { apiGet, apiDelete, fetchSSE } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import { readSSE } from "@/lib/sse";
import type { ConversationList, Message } from "../types/types";
import { chatSSEEvent, type ChatSSEEvent } from "./chat.schema";

/**
 * Lists conversations for a project.
 */
export function listConversations(
  projectId: string,
): Promise<Result<ConversationList>> {
  return attempt(() =>
    apiGet<ConversationList>(`/projects/${projectId}/conversations`),
  );
}

/**
 * Gets messages for a conversation.
 */
export function getMessages(
  conversationId: string,
): Promise<Result<Message[]>> {
  return attempt(() =>
    apiGet<Message[]>(`/conversations/${conversationId}/messages`),
  );
}

/**
 * Deletes a conversation.
 */
export function deleteConversation(
  conversationId: string,
): Promise<Result<void>> {
  return attempt(() => apiDelete(`/conversations/${conversationId}`));
}

/**
 * Sends a chat message and returns the raw SSE response for streaming.
 *
 * Stays outside `Result<T>`: it hands back a transport object, not a domain
 * type, so the caller reads `response.ok` itself. `conversationId` is `null` to
 * open a new conversation.
 */
export function chatStream(
  projectId: string,
  message: string,
  conversationId: string | null,
): Promise<Response> {
  return fetchSSE(`/projects/${projectId}/chat`, {
    message,
    conversation_id: conversationId,
  });
}

/**
 * Chat events, validated against the backend contract.
 *
 * Throws on an event the contract does not name — a key the backend renamed
 * used to be dropped in silence. `chatStream` stays as it is: three frozen
 * cases pin it to a raw `Response`.
 */
export async function* streamChat(
  projectId: string,
  message: string,
  conversationId: string | null,
): AsyncGenerator<ChatSSEEvent> {
  const response = await chatStream(projectId, message, conversationId);

  for await (const raw of readSSE(response)) {
    yield chatSSEEvent.parse(raw);
  }
}
