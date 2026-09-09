import { Bot, User, Copy, Check } from "lucide-react";
import { useState, useMemo } from "react";
import Markdown from "react-markdown";
import { cn } from "@/lib/utils";
import type { StreamingMessage } from "../types/types";
import { ChatSources } from "./ChatSources";
import { ChatStructuredSchema } from "./ChatStructuredSchema";
import { ChatStructuredTable } from "./ChatStructuredTable";

function formatMessageTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const isToday =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  if (isToday) {
    return date.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return date.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface ChatMessageProps {
  message: StreamingMessage;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const markdownContent = useMemo(
    () => (
      <div className="prose-chat">
        <Markdown>{message.content}</Markdown>
      </div>
    ),
    [message.content],
  );

  function handleCopy(): void {
    navigator.clipboard
      .writeText(message.content)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {
        console.error("Failed to copy to clipboard");
      });
  }

  return (
    <article
      className={cn(
        "group flex w-full items-start gap-3",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
            : "bg-[hsl(var(--muted))] text-[hsl(var(--primary))]",
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      <div className={cn("max-w-[80%]", isUser ? "text-right" : "text-left")}>
        <div
          className={cn(
            "rounded-lg px-4 py-3 text-sm",
            isUser
              ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
              : "bg-[hsl(var(--secondary))] text-[hsl(var(--foreground))]",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-left">{message.content}</p>
          ) : (
            markdownContent
          )}
          {!isUser && message.structured && (
            <ChatStructuredTable table={message.structured} />
          )}
          {!isUser && message.schema && (
            <ChatStructuredSchema
              schema={message.schema}
              delay={message.structured ? 0.6 + message.structured.rows.length * 0.18 : 0}
            />
          )}
          {!isUser && message.sources.length > 0 && (
            <ChatSources sources={message.sources} />
          )}
        </div>

        <div
          className={cn(
            "mt-1 flex items-center gap-2 text-[11px] text-[hsl(var(--muted-foreground))]",
            isUser ? "justify-end" : "justify-start",
          )}
        >
          {message.created_at && (
            <time dateTime={message.created_at}>
              {formatMessageTime(message.created_at)}
            </time>
          )}
          {!isUser && message.content && (
            <button
              type="button"
              onClick={handleCopy}
              className="opacity-0 transition-opacity group-hover:opacity-100 hover:text-[hsl(var(--foreground))]"
              aria-label="Copier la réponse"
            >
              {copied ? (
                <Check className="h-3 w-3" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
