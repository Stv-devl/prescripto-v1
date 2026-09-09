import { AlertTriangle, FileText } from "lucide-react";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";

interface ProjectSummaryTabGateProps {
  isPending: boolean;
  hasError: boolean;
  hasDocuments: boolean;
}

/**
 * The three states that block `ProjectSummaryTab` before any summary can be
 * shown: loading, status-load failure, no documents — in that priority
 * order. Returns `null` when none apply, meaning the caller should proceed.
 */
export function ProjectSummaryTabGate({
  isPending,
  hasError,
  hasDocuments,
}: ProjectSummaryTabGateProps): React.ReactElement | null {
  if (isPending) {
    return (
      <section
        className="h-full flex items-center justify-center"
        aria-label="Résumé du projet"
      >
        <LoadingSpinner size="lg" />
      </section>
    );
  }

  if (hasError) {
    return (
      <section
        className="h-full overflow-y-auto p-6"
        aria-label="Résumé du projet"
      >
        <div className="max-w-xl mx-auto py-12 text-center">
          <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-red-400">
            Impossible de charger le statut du résumé.
          </p>
        </div>
      </section>
    );
  }

  if (!hasDocuments) {
    return (
      <section
        className="h-full overflow-y-auto p-6"
        aria-label="Résumé du projet"
      >
        <div className="max-w-xl mx-auto py-12 text-center">
          <FileText className="h-10 w-10 text-[hsl(var(--muted-foreground))] mx-auto mb-4 opacity-40" />
          <h3 className="text-base font-semibold text-[hsl(var(--foreground))] mb-2">
            Aucun document
          </h3>
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Importez des documents dans l'onglet Documents pour générer un
            résumé IA du projet.
          </p>
        </div>
      </section>
    );
  }

  return null;
}
