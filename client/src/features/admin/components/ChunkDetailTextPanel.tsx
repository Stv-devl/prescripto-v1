import type { RefObject } from "react";
import type { ChunkDetail } from "../types/types";

interface ChunkDetailTextPanelProps {
  chunk: ChunkDetail;
  isEditing: boolean;
  editText: string;
  onEditTextChange: (text: string) => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

export function ChunkDetailTextPanel({
  chunk,
  isEditing,
  editText,
  onEditTextChange,
  textareaRef,
}: ChunkDetailTextPanelProps) {
  return (
    <section>
      <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
        {isEditing ? "Édition du texte" : "Texte complet"}
      </h3>
      {isEditing ? (
        <div className="space-y-2">
          <textarea
            ref={textareaRef}
            value={editText}
            onChange={(e) => onEditTextChange(e.target.value)}
            rows={15}
            className="w-full resize-y rounded-lg border border-[#FFC300]/50 bg-[hsl(var(--background))] p-4 text-sm leading-relaxed text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
          />
          <p className="text-xs text-[hsl(var(--muted-foreground))]">
            {editText.length} caractères — Pour scinder, placez le curseur et cliquez "Scinder"
          </p>
        </div>
      ) : (
        <pre className="max-h-[300px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-[hsl(var(--secondary))]/50 p-4 text-sm leading-relaxed text-[hsl(var(--foreground))]">
          {chunk.text}
        </pre>
      )}
    </section>
  );
}
