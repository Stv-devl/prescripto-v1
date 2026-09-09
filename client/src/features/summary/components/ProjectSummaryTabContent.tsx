import type { ProjectSummaryData } from "../types/types";
import { ProjectSummaryTabConstructifEntry } from "./ProjectSummaryTabConstructifEntry";
import { ProjectSummaryTabContrainteEntry } from "./ProjectSummaryTabContrainteEntry";

interface ProjectSummaryTabContentProps {
  data: ProjectSummaryData;
  projectName: string;
}

/** The project summary report: description, structural system, constraints. */
export function ProjectSummaryTabContent({
  data,
  projectName,
}: ProjectSummaryTabContentProps): React.ReactElement {
  return (
    <div className="max-w-6xl space-y-6 pb-12">
      {/* Description */}
      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
        <header className="mb-3">
          <h2 className="text-base font-semibold text-[hsl(var(--foreground))] tracking-tight">
            {projectName}
          </h2>
        </header>
        <p className="text-sm leading-relaxed text-[hsl(var(--muted-foreground))]">
          {data.description}
        </p>
      </article>

      {/* Structural system */}
      {data.systemeConstructif?.length > 0 && (
        <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
          <header className="mb-1">
            <h2 className="text-base font-semibold text-[hsl(var(--foreground))] tracking-tight">
              Système constructif
            </h2>
          </header>
          <dl className="divide-y divide-[hsl(var(--border))]">
            {data.systemeConstructif.map((item, i) => (
              <ProjectSummaryTabConstructifEntry key={item.label} item={item} index={i} />
            ))}
          </dl>
        </article>
      )}

      {/* Contraintes */}
      {data.contraintes?.length > 0 && (
        <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
          <header className="mb-1">
            <h2 className="text-base font-semibold text-[hsl(var(--foreground))] tracking-tight">
              Contraintes techniques & réglementaires
            </h2>
          </header>
          <dl className="grid gap-x-8 sm:grid-cols-2 sm:divide-y-0">
            {data.contraintes.map((item) => (
              <ProjectSummaryTabContrainteEntry key={item.label} item={item} />
            ))}
          </dl>
        </article>
      )}
    </div>
  );
}
