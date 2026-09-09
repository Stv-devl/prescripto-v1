import { AlertTriangle, Bot, RefreshCw } from "lucide-react";

interface ProjectSummaryTabNoActiveGenerationProps {
  error: string | null;
  onRegenerate: () => void;
}

/**
 * No cached summary and nothing currently generating: either the last
 * generation attempt failed, or the project is simply ready for its first
 * one.
 */
export function ProjectSummaryTabNoActiveGeneration({
  error,
  onRegenerate,
}: ProjectSummaryTabNoActiveGenerationProps): React.ReactElement {
  if (error) {
    return (
      <div className="max-w-xl mx-auto py-12 text-center">
        <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-3" />
        <p className="text-sm text-red-400 mb-4">{error}</p>
        <button
          type="button"
          onClick={onRegenerate}
          className="inline-flex items-center gap-2 rounded-lg bg-[#FFC300] px-5 py-2.5 text-sm font-semibold text-black hover:bg-[#FFD000] transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Réessayer
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto py-12 text-center">
      <Bot className="h-10 w-10 text-[#FFC300] mx-auto mb-4 animate-pulse" />
      <h3 className="text-base font-semibold text-[hsl(var(--foreground))] mb-2">
        Résumé IA disponible
      </h3>
      <p className="text-sm text-[hsl(var(--muted-foreground))] mb-6">
        Analysez automatiquement les documents du projet pour générer un
        résumé technique structuré.
      </p>
      <button
        type="button"
        onClick={onRegenerate}
        className="inline-flex items-center gap-2 rounded-lg bg-[#FFC300] px-5 py-2.5 text-sm font-semibold text-black hover:bg-[#FFD000] transition-colors"
      >
        <Bot className="h-4 w-4" />
        Générer le résumé
      </button>
    </div>
  );
}
