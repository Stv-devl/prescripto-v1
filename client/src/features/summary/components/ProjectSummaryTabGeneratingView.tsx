import { Bot, Loader2 } from "lucide-react";
import type { SummaryProgressEvent } from "../types/types";

const CONTRAINTE_LABELS = new Set([
  "Réglementation thermique",
  "Vent & Pluie",
  "Sismique",
  "Contraintes constructives",
]);

function formatStepLabel(section: string): string {
  return CONTRAINTE_LABELS.has(section) ? "Contraintes" : section;
}

interface ProjectSummaryTabGeneratingViewProps {
  progress: SummaryProgressEvent[];
  total: number;
}

/** SSE progress view shown while the project summary is being generated. */
export function ProjectSummaryTabGeneratingView({
  progress,
  total,
}: ProjectSummaryTabGeneratingViewProps): React.ReactElement {
  const completed = progress.length;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="max-w-md mx-auto py-12">
      <div className="text-center mb-8">
        <Bot className="h-8 w-8 text-[#FFC300] mx-auto mb-3 animate-pulse" />
        <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-1">
          Génération du résumé
        </h3>
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          {completed}/{total} sections analysées
        </p>
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="h-1.5 rounded-full bg-[hsl(var(--muted))] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#FFC300] transition-all duration-500 ease-out"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      {/* Current step — single line, cycles through each step */}
      <div className="flex justify-center">
        {completed < total ? (
          <span
            key={completed}
            className="inline-flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] animate-[fadeSlideIn_0.3s_ease-out]"
          >
            <Loader2 className="h-3.5 w-3.5 text-[#FFC300] shrink-0 animate-spin" />
            {progress.length > 0
              ? formatStepLabel(progress[progress.length - 1].section)
              : "Analyse en cours..."}
          </span>
        ) : (
          <span className="inline-flex items-center gap-2 text-sm text-[#FFC300] animate-[fadeSlideIn_0.3s_ease-out]">
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
            Finalisation...
          </span>
        )}
      </div>
    </div>
  );
}
