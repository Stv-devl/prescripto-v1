import { useEffect, useRef, useState, useCallback } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import type { Message, StreamingMessage } from "../types/types";
import { ChatInput } from "./ChatInput";
import { ChatMessage } from "./ChatMessage";
import { ChatWelcome } from "./ChatWelcome";
import { ThinkingIndicator } from "./ThinkingIndicator";

/** How often the scroll follows a growing message, in ms. */
const FOLLOW_INTERVAL_MS = 50;
/** How long to keep following, in ms — the longest expand animation. */
const FOLLOW_DURATION_MS = 3000;

interface ChatPanelProps {
  /** Persisted messages from the selected conversation. */
  historyMessages: Message[];
  /** Live streaming messages from current session. */
  streamingMessages: StreamingMessage[];
  isStreaming: boolean;
  isPending: boolean;
  error: Error | null;
  onSend: (text: string) => void;
}

export function ChatPanel({
  historyMessages,
  streamingMessages,
  isStreaming,
  isPending,
  error,
  onSend,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  const allMessages: StreamingMessage[] = [
    ...historyMessages.map((m) => ({
      role: m.role,
      content: m.content,
      sources: m.sources,
      structured: m.structured ?? null,
      schema: m.schema ?? null,
      created_at: m.created_at,
    })),
    ...streamingMessages,
  ];

  const smoothScrollToBottom = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    const container = scrollContainerRef.current;
    if (!container) return;

    const step = (): void => {
      const gap =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      if (gap > 1) {
        container.scrollTop += Math.max(gap * 0.025, 1);
        rafRef.current = requestAnimationFrame(step);
      } else {
        container.scrollTop = container.scrollHeight;
      }
    };
    rafRef.current = requestAnimationFrame(step);
  }, []);

  const lastMessageContent = allMessages[allMessages.length - 1]?.content;

  useEffect(() => {
    smoothScrollToBottom();
  }, [allMessages.length, lastMessageContent, smoothScrollToBottom]);

  const lastMsg = allMessages[allMessages.length - 1];
  const hasVisuals = lastMsg?.structured || lastMsg?.schema;
  const prevHeightRef = useRef(0);

  useEffect(() => {
    if (!hasVisuals) return;

    const container = scrollContainerRef.current;
    if (!container) return;

    prevHeightRef.current = container.scrollHeight;

    const poll = setInterval(() => {
      const newHeight = container.scrollHeight;
      if (newHeight !== prevHeightRef.current) {
        prevHeightRef.current = newHeight;
        smoothScrollToBottom();
      }
    }, FOLLOW_INTERVAL_MS);

    const timeout = setTimeout(() => clearInterval(poll), FOLLOW_DURATION_MS);

    return () => {
      clearInterval(poll);
      clearTimeout(timeout);
    };
  }, [hasVisuals, smoothScrollToBottom]);

  const [showThinking, setShowThinking] = useState(false);
  useEffect(() => {
    if (isStreaming) {
      setShowThinking(true);
    } else if (showThinking) {
      const timer = setTimeout(() => setShowThinking(false), 400);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, showThinking]);

  const isEmpty = !isPending && allMessages.length === 0;

  if (isEmpty) {
    return (
      <section
        className="flex h-full flex-col items-center justify-center px-4"
        aria-label="Chat"
      >
        <div className="flex w-full max-w-2xl flex-col items-center gap-8">
          <ChatWelcome onSuggestion={onSend} />
          <div className="w-full">
            <ChatInput onSend={onSend} disabled={isStreaming} centered />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full flex-col" aria-label="Chat">
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4">
        {isPending && (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        )}

        {error && <ErrorMessage error={error} />}

        <div className="mx-auto flex max-w-3xl flex-col gap-3">
          {allMessages.map((msg, i) => {
            const isThinkingVisible =
              showThinking &&
              msg.role === "assistant" &&
              i === allMessages.length - 1;

            return (
              <div key={i} className="flex flex-col gap-3">
                {isThinkingVisible && (
                  <div
                    className={`flex justify-center transition-all duration-300 ${
                      isStreaming
                        ? "opacity-100 max-h-12"
                        : "opacity-0 max-h-0 overflow-hidden"
                    }`}
                  >
                    <ThinkingIndicator />
                  </div>
                )}
                <ChatMessage message={msg} />
              </div>
            );
          })}

          {showThinking && !allMessages.some((m) => m.role === "assistant") && (
            <div
              className={`flex justify-center transition-all duration-300 ${
                isStreaming
                  ? "opacity-100 max-h-12"
                  : "opacity-0 max-h-0 overflow-hidden"
              }`}
            >
              <ThinkingIndicator />
            </div>
          )}
        </div>

        <div ref={bottomRef} />
      </div>

      <div className="mx-auto w-full max-w-3xl">
        <ChatInput onSend={onSend} disabled={isStreaming} />
      </div>
    </section>
  );
}
