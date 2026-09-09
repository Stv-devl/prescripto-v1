import { Bot } from "lucide-react";

const SUGGESTIONS = [
  "Quels sont les lots du CCTP ?",
  "Résume le descriptif technique",
  "Liste les matériaux mentionnés",
  "Quelles sont les contraintes du projet ?",
];

interface ChatWelcomeProps {
  onSuggestion: (text: string) => void;
}

/**
 * Welcome screen shown when no messages exist in the conversation.
 * Displays suggested questions that pre-fill the chat input.
 */
export function ChatWelcome({ onSuggestion }: ChatWelcomeProps) {
  return (
    <div className="flex flex-col items-center gap-6 px-4">
      <div className="flex size-14 items-center justify-center rounded-full bg-[hsl(var(--muted))]">
        <Bot className="h-7 w-7 text-[hsl(var(--primary))]" />
      </div>

      <div className="text-center">
        <h2 className="text-lg font-semibold">Interrogez vos documents</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Posez une question pour commencer la conversation.
        </p>
      </div>

      <nav
        className="flex flex-wrap justify-center gap-2"
        aria-label="Suggestions"
      >
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            type="button"
            onClick={() => onSuggestion(text)}
            className="rounded-full border border-[hsl(var(--border))] px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
          >
            {text}
          </button>
        ))}
      </nav>
    </div>
  );
}
