import { AlertTriangle, RefreshCw } from "lucide-react";
import { useSummaryStatus, useSummary, useSummaryGeneration } from "../hooks/hooks";
import { ProjectSummaryTabContent } from "./ProjectSummaryTabContent";
import { ProjectSummaryTabGate } from "./ProjectSummaryTabGate";
import { ProjectSummaryTabGeneratingView } from "./ProjectSummaryTabGeneratingView";
import { ProjectSummaryTabNoActiveGeneration } from "./ProjectSummaryTabNoActiveGeneration";

interface ProjectSummaryTabProps {
  projectId: string;
  projectName: string;
}

/**
 * Project summary tab — structured technical report view.
 * Displays construction system details and regulatory constraints
 * with inline SVG cross-section schemas.
 * Uses AI-generated summaries from the backend with SSE streaming.
 */
export function ProjectSummaryTab({
  projectId,
  projectName,
}: ProjectSummaryTabProps): React.ReactElement {
  const status = useSummaryStatus(projectId);
  const hasSummary = status.data?.has_summary ?? false;
  const summary = useSummary(projectId, hasSummary);
  const generation = useSummaryGeneration(projectId);

  const gate = ProjectSummaryTabGate({
    isPending: status.isPending,
    hasError: !!status.error,
    hasDocuments: status.data?.has_documents ?? false,
  });
  if (gate) return gate;

  // ── Generation in progress ──
  if (generation.isGenerating) {
    return (
      <section
        className="h-full overflow-y-auto p-6"
        aria-label="Résumé du projet"
      >
        <ProjectSummaryTabGeneratingView
          progress={generation.progress}
          total={
            generation.progress.length > 0 ? generation.progress[0].total : 12
          }
        />
      </section>
    );
  }

  // ── Generation just completed (data from SSE, before query refetch) ──
  if (generation.generatedData) {
    return (
      <section
        className="h-full overflow-y-auto p-6"
        aria-label="Résumé du projet"
      >
        {generation.finalStatus === "partial" && (
          <div className="max-w-6xl mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-500">
            <AlertTriangle className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            Certaines sections n'ont pas pu être extraites. Le résumé est
            partiel.
          </div>
        )}
        <ProjectSummaryTabContent
          data={generation.generatedData}
          projectName={projectName}
        />
        <div className="max-w-6xl mt-4">
          <button
            type="button"
            onClick={generation.generate}
            className="inline-flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] px-4 py-2 text-sm font-medium text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Régénérer le résumé
          </button>
        </div>
      </section>
    );
  }

  // ── Cached summary exists ──
  if (hasSummary && summary.data?.data) {
    const summaryStatus = summary.data.status;
    return (
      <section
        className="h-full overflow-y-auto p-6"
        aria-label="Résumé du projet"
      >
        {generation.error && (
          <div
            role="alert"
            className="max-w-6xl mb-4 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400"
          >
            <AlertTriangle className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            {generation.error}
            <span className="mt-1 block opacity-80">
              Le résumé affiché est le précédent.
            </span>
          </div>
        )}
        {summaryStatus === "partial" && (
          <div className="max-w-6xl mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-500">
            <AlertTriangle className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            Certaines sections n'ont pas pu être extraites. Le résumé est
            partiel.
          </div>
        )}
        {summaryStatus === "error" && (
          <div className="max-w-6xl mb-4 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            <AlertTriangle className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            La génération a échoué.
            {summary.data.error_message && ` ${summary.data.error_message}`}
          </div>
        )}
        <ProjectSummaryTabContent data={summary.data.data} projectName={projectName} />
        <div className="max-w-6xl mt-4">
          <button
            type="button"
            onClick={generation.generate}
            className="inline-flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] px-4 py-2 text-sm font-medium text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Régénérer le résumé
          </button>
        </div>
      </section>
    );
  }

  // ── No cached summary, nothing generating: failed attempt or first-time ──
  return (
    <section
      className="h-full overflow-y-auto p-6"
      aria-label="Résumé du projet"
    >
      <ProjectSummaryTabNoActiveGeneration
        error={generation.error}
        onRegenerate={generation.generate}
      />
    </section>
  );
}
