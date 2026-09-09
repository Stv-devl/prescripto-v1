import { Send } from "lucide-react";
import { useState, useRef, useCallback, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  centered?: boolean;
}

const MAX_ROWS = 5;
/** Line height of `text-sm`, in px. Tracks the textarea's own class. */
const LINE_HEIGHT = 20;
/** Vertical padding of `py-2`, in px: 8 top plus 8 bottom. */
const PADDING_Y = 16;

export function ChatInput({
  onSend,
  disabled,
  centered = false,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = LINE_HEIGHT * MAX_ROWS + PADDING_Y;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  function handleChange(value: string): void {
    setText(value);
    requestAnimationFrame(autoResize);
  }

  function handleSend(): void {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (el) el.style.height = "auto";
    });
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <footer
      className={cn(
        "shrink-0 px-4 pb-3 pt-3",
        !centered && "border-t border-[hsl(var(--border))]",
      )}
    >
      <div
        className={cn(
          "flex items-end gap-2",
          centered &&
            "rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-2 shadow-sm",
        )}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez une question sur vos documents…"
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-5 text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none",
            !centered &&
              "rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] focus:ring-2 focus:ring-[hsl(var(--ring))]",
          )}
          disabled={disabled}
        />
        <Button
          size="icon"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          aria-label="Envoyer"
          className={cn(centered && "rounded-lg")}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
      <p className="mt-1.5 text-center text-[11px] italic text-gray-500">
        Enter pour envoyer · Shift+Enter pour un retour à la ligne
      </p>
    </footer>
  );
}
