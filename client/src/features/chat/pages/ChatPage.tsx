import { ArrowLeft } from "lucide-react";
import { useState, useCallback, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { ChatPanel } from "../components/ChatPanel";
import { ConversationSidebar } from "../components/ConversationSidebar";
import {
  useConversations,
  useMessages,
  useChatStream,
  useDeleteConversation,
} from "../hooks/hooks";

export function ChatPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);

  const conversations = useConversations(projectId!);
  const chat = useChatStream(projectId!);
  const deleteConv = useDeleteConversation(projectId!);

  const sidebarConvId = selectedConvId ?? chat.conversationId;

  useEffect(() => {
    if (!selectedConvId && chat.conversationId && !chat.isStreaming) {
      setSelectedConvId(chat.conversationId);
    }
  }, [chat.conversationId, chat.isStreaming, selectedConvId]);

  const messages = useMessages(selectedConvId);

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

  return (
    <main className="flex h-[calc(100vh-3.5rem)] flex-col">
      <header className="flex items-center gap-2 border-b border-[hsl(var(--border))] px-4 py-2">
        <Link
          to={`/projects/${projectId}`}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-[hsl(var(--foreground))]"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour au projet
        </Link>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ConversationSidebar
          conversations={conversations.data?.conversations ?? []}
          selectedId={sidebarConvId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          isPending={conversations.isPending}
        />

        <div className="flex-1">
          <ChatPanel
            historyMessages={messages.data ?? []}
            streamingMessages={chat.messages}
            isStreaming={chat.isStreaming}
            isPending={!!selectedConvId && messages.isPending && chat.messages.length === 0}
            error={messages.error}
            onSend={handleSend}
          />
        </div>
      </div>
    </main>
  );
}
