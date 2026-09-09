import { motion } from "framer-motion";
import { Bookmark, ChevronUp, ChevronDown } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import { useProjectsViewStore } from "../stores/projectsViewStore";
import type { Project } from "../types/types";
import { ProjectContextMenu } from "./ProjectContextMenu";

interface ProjectListTableProps {
  projects: Project[];
  onDelete: (id: string) => void;
  onArchive: (id: string) => void;
  onToggleFavorite: (id: string) => void;
}

type SortableColumn = "name" | "created_at" | "document_count";

const COLUMNS = [
  { key: "name" as const, label: "Nom", sortable: true },
  { key: "client" as const, label: "Client", sortable: false },
  { key: "phase" as const, label: "Phase", sortable: false },
  { key: "status" as const, label: "Statut", sortable: false },
  { key: "document_count" as const, label: "Documents", sortable: true },
  { key: "created_at" as const, label: "Date", sortable: true },
  { key: "actions" as const, label: "", sortable: false },
] as const;

export function ProjectListTable({
  projects,
  onDelete,
  onArchive,
  onToggleFavorite,
}: ProjectListTableProps) {
  const navigate = useNavigate();
  const sortBy = useProjectsViewStore((s) => s.sortBy);
  const sortDirection = useProjectsViewStore((s) => s.sortDirection);
  const setSortBy = useProjectsViewStore((s) => s.setSortBy);
  const setSortDirection = useProjectsViewStore((s) => s.setSortDirection);

  function handleSort(column: SortableColumn): void {
    if (sortBy === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortBy(column);
      setSortDirection(column === "name" ? "asc" : "desc");
    }
  }

  function SortIcon({ column }: { column: SortableColumn }): React.ReactElement | null {
    if (sortBy !== column) return null;
    return sortDirection === "asc" ? (
      <ChevronUp className="h-3.5 w-3.5" />
    ) : (
      <ChevronDown className="h-3.5 w-3.5" />
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[hsl(var(--border))]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--secondary))]">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]",
                  col.sortable && "cursor-pointer select-none hover:text-[hsl(var(--foreground))]",
                )}
                onClick={
                  col.sortable
                    ? () => handleSort(col.key as SortableColumn)
                    : undefined
                }
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  {col.sortable && <SortIcon column={col.key as SortableColumn} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {projects.map((project) => {
            const date = new Date(project.created_at).toLocaleDateString(
              "fr-FR",
              { day: "numeric", month: "short", year: "numeric" },
            );
            const isArchived = project.status === "archived";

            return (
              <motion.tr
                key={project.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="cursor-pointer border-b border-[hsl(var(--border))] transition-colors last:border-b-0 hover:bg-[hsl(var(--muted))]/50"
                onClick={() => navigate(`/projects/${project.id}`)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
              >
                <td className="px-4 py-3 font-medium">{project.name}</td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  {project.client || "—"}
                </td>
                <td className="px-4 py-3">
                  {project.phase ? (
                    <Badge variant="outline">{project.phase}</Badge>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  <Badge
                    className={cn(
                      "text-[10px]",
                      isArchived
                        ? "border-transparent bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]"
                        : "border-transparent bg-emerald-500/15 text-emerald-400",
                    )}
                  >
                    {isArchived ? "Archivé" : "Actif"}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  {project.document_count}
                </td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  <time dateTime={project.created_at}>{date}</time>
                </td>
                <td className="px-4 py-3">
                  <div
                    className="flex items-center gap-1"
                    role="presentation"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleFavorite(project.id);
                      }}
                      className="rounded p-1 transition-colors hover:bg-[hsl(var(--muted))]"
                      aria-label={
                        project.is_favorite
                          ? "Retirer des favoris"
                          : "Ajouter aux favoris"
                      }
                    >
                      <Bookmark
                        className={cn(
                          "h-4 w-4",
                          project.is_favorite
                            ? "fill-[#FFC300] text-[#FFC300]"
                            : "text-[hsl(var(--muted-foreground))]",
                        )}
                      />
                    </button>
                    <ProjectContextMenu
                      project={project}
                      onOpen={() => navigate(`/projects/${project.id}`)}
                      onArchive={() => onArchive(project.id)}
                      onDelete={() => onDelete(project.id)}
                    />
                  </div>
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
