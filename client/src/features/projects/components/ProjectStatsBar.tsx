import { FolderOpen, FileText, Activity, Archive } from "lucide-react";
import type { Project } from "../types/types";

interface ProjectStatsBarProps {
  projects: Project[];
}

export function ProjectStatsBar({ projects }: ProjectStatsBarProps) {
  const totalDocs = projects.reduce((sum, p) => sum + p.document_count, 0);
  const active = projects.filter((p) => p.status === "active").length;
  const archived = projects.filter((p) => p.status === "archived").length;

  const stats = [
    { label: "Projets", value: projects.length, icon: FolderOpen },
    { label: "Documents", value: totalDocs, icon: FileText },
    { label: "Actifs", value: active, icon: Activity },
    { label: "Archivés", value: archived, icon: Archive },
  ];

  return (
    <section
      className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4"
      aria-label="Statistiques des projets"
    >
      {stats.map((stat) => (
        <article
          key={stat.label}
          className="flex items-center gap-3 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-4 py-3"
        >
          <stat.icon
            className="h-5 w-5 shrink-0 text-[hsl(var(--muted-foreground))]"
            aria-hidden="true"
          />
          <div>
            <p className="text-lg font-semibold leading-tight">{stat.value}</p>
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              {stat.label}
            </p>
          </div>
        </article>
      ))}
    </section>
  );
}
