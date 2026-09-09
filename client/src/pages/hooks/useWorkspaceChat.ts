import { useState, useCallback, useEffect } from "react";
import {
  useConversations,
  useMessages,
  useChatStream,
  useDeleteConversation,
} from "@/features/chat";

/**
 * Encapsulates all chat state and handlers
 * for the ProjectWorkspacePage chat tab.
 */
export function useWorkspaceChat(projectId: string) {
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const conversations = useConversations(projectId);
  const chat = useChatStream(projectId);
  const deleteConv = useDeleteConversation(projectId);
  const messages = useMessages(selectedConvId);

  const sidebarConvId = selectedConvId ?? chat.conversationId;

  useEffect(() => {
    if (!selectedConvId && chat.conversationId && !chat.isStreaming) {
      setSelectedConvId(chat.conversationId);
    }
  }, [chat.conversationId, chat.isStreaming, selectedConvId]);

  const handleNewConversation = useCallback(() => {
    setSelectedConvId(null);
    chat.reset();
  }, [chat]);

  const handleSelectConversation = useCallback(
    (id: string) => {
      setSelectedConvId(id);
      chat.reset();
    },
    [chat],
  );

  const handleDeleteConversation = useCallback(
    (id: string) => {
      deleteConv.mutate(id, {
        onSuccess: () => {
          if (selectedConvId === id) {
            setSelectedConvId(null);
            chat.reset();
          }
        },
      });
    },
    [deleteConv, selectedConvId, chat],
  );

  const handleSend = useCallback(
    (text: string) => {
      chat.sendMessage(text, selectedConvId);
    },
    [chat, selectedConvId],
  );

  return {
    selectedConvId,
    sidebarConvId,
    conversations,
    chat,
    messages,
    handleNewConversation,
    handleSelectConversation,
    handleDeleteConversation,
    handleSend,
  } as const;
}
