import { Bookmark, Calendar, FileText, MapPin } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import type { Project } from "../types/types";
import { DeleteProjectModal } from "./DeleteProjectModal";
import { ProjectContextMenu } from "./ProjectContextMenu";

interface ProjectCardProps {
  project: Project;
  onDelete?: (id: string) => void;
  onArchive?: (id: string) => void;
  onToggleFavorite?: (id: string) => void;
  isDeleting?: boolean;
}

export function ProjectCard({
  project,
  onDelete,
  onArchive,
  onToggleFavorite,
  isDeleting,
}: ProjectCardProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const navigate = useNavigate();

  const date = new Date(project.created_at).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const isArchived = project.status === "archived";

  return (
    <>
      <Card
        className="cursor-pointer transition-colors hover:border-[hsl(var(--primary))]/40"
        onClick={() => navigate(`/projects/${project.id}`)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        <CardContent className="flex flex-col gap-3">
          <header className="flex items-start justify-between">
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-lg font-semibold">{project.name}</h3>
              {project.client && (
                <p className="truncate text-sm text-[hsl(var(--muted-foreground))]">
                  {project.client}
                </p>
              )}
            </div>
            <div className="ml-2 flex shrink-0 items-center gap-1">
              {project.phase && (
                <Badge variant="outline">{project.phase}</Badge>
              )}
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
            </div>
          </header>

          {project.address && (
            <p className="flex items-center gap-1 truncate text-sm text-[hsl(var(--muted-foreground))]">
              <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {project.address}
            </p>
          )}

          <footer className="flex items-center justify-between text-sm text-[hsl(var(--muted-foreground))]">
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
                <time dateTime={project.created_at}>{date}</time>
              </span>
              <span className="inline-flex items-center gap-1">
                <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                {project.document_count} doc
                {project.document_count !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="flex items-center gap-1">
              {onToggleFavorite && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
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
              )}
              {onDelete && (
                <ProjectContextMenu
                  project={project}
                  onOpen={() => navigate(`/projects/${project.id}`)}
                  onArchive={() => onArchive?.(project.id)}
                  onDelete={() => {
                    if (!isDeleting) setShowDeleteModal(true);
                  }}
                />
              )}
            </div>
          </footer>
        </CardContent>
      </Card>

      {showDeleteModal && (
        <DeleteProjectModal
          projectName={project.name}
          isPending={isDeleting ?? false}
          onConfirm={() => onDelete?.(project.id)}
          onClose={() => setShowDeleteModal(false)}
        />
      )}
    </>
  );
}
