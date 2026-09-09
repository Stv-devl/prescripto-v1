import { FolderOpen, Plus, Upload } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { CreateProjectModal } from "../components/CreateProjectModal";
import { ProjectCard } from "../components/ProjectCard";
import { ProjectFilters } from "../components/ProjectFilters";
import { ProjectListTable } from "../components/ProjectListTable";
import { ProjectSearchBar } from "../components/ProjectSearchBar";
import { ProjectStatsBar } from "../components/ProjectStatsBar";
import { ViewToggle } from "../components/ViewToggle";
import {
  useProjects,
  useDeleteProject,
  useToggleFavorite,
  useArchiveProject,
} from "../hooks/hooks";
import { useFilteredProjects } from "../hooks/useFilteredProjects";
import { useProjectsPageDrop } from "../hooks/useProjectsPageDrop";
import { useProjectsViewStore } from "../stores/projectsViewStore";

export function ProjectsPage() {
  const [showModal, setShowModal] = useState(false);
  const { data, isPending, error, refetch } = useProjects();
  const deleteProject = useDeleteProject();
  const toggleFavorite = useToggleFavorite();
  const archiveProject = useArchiveProject();
  const drop = useProjectsPageDrop();

  const viewMode = useProjectsViewStore((s) => s.viewMode);
  const allProjects = data?.projects ?? [];
  const { filtered, favorites, nonFavorites } =
    useFilteredProjects(allProjects);

  function handleToggleFavorite(projectId: string): void {
    const project = allProjects.find((p) => p.id === projectId);
    if (project) {
      toggleFavorite.mutate({
        projectId,
        isFavorite: project.is_favorite,
      });
    }
  }

  function handleArchive(projectId: string): void {
    const project = allProjects.find((p) => p.id === projectId);
    if (project) {
      archiveProject.mutate({
        projectId,
        currentStatus: project.status,
      });
    }
  }

  return (
    <main
      className="relative p-6"
      onDragEnter={drop.onDragEnter}
      onDragOver={drop.onDragOver}
      onDragLeave={drop.onDragLeave}
      onDrop={drop.onDrop}
    >
      {drop.isCreating && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center gap-3 rounded-lg bg-[hsl(var(--background))]/80 backdrop-blur-sm">
          <LoadingSpinner size="lg" />
          <p className="text-sm font-medium text-muted-foreground">
            Création du projet et import des fichiers…
          </p>
        </div>
      )}

      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projets</h1>
        <div className="flex items-center gap-3">
          <ViewToggle />
          <Button onClick={() => setShowModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nouveau projet
          </Button>
        </div>
      </header>

      {isPending && (
        <div className="flex justify-center py-12">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {error && <ErrorMessage error={error} onRetry={() => void refetch()} />}

      {data && allProjects.length > 0 && (
        <>
          <ProjectStatsBar projects={allProjects} />

          <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="w-full max-w-sm">
              <ProjectSearchBar />
            </div>
            <ProjectFilters />
          </div>

          {favorites.length > 0 && (
            <section className="mb-6" aria-label="Projets favoris">
              <h2 className="mb-3 text-sm font-medium text-[hsl(var(--muted-foreground))]">
                Favoris
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {favorites.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onDelete={(id) => deleteProject.mutate(id)}
                    onArchive={handleArchive}
                    onToggleFavorite={handleToggleFavorite}
                    isDeleting={deleteProject.isPending}
                  />
                ))}
              </div>
            </section>
          )}

          {nonFavorites.length > 0 && (
            <>
              {viewMode === "grid" ? (
                <section
                  className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                  aria-label="Liste des projets"
                >
                  {nonFavorites.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onDelete={(id) => deleteProject.mutate(id)}
                      onArchive={handleArchive}
                      onToggleFavorite={handleToggleFavorite}
                      isDeleting={deleteProject.isPending}
                    />
                  ))}
                </section>
              ) : (
                <ProjectListTable
                  projects={nonFavorites}
                  onDelete={(id) => deleteProject.mutate(id)}
                  onArchive={handleArchive}
                  onToggleFavorite={handleToggleFavorite}
                />
              )}
            </>
          )}

          {filtered.length === 0 && (
            <EmptyState
              icon={<FolderOpen className="h-10 w-10" />}
              message="Aucun projet ne correspond aux filtres"
              description="Essayez de modifier vos critères de recherche ou de réinitialiser les filtres."
            />
          )}
        </>
      )}

      {data && allProjects.length === 0 && (
        <EmptyState
          icon={<FolderOpen className="h-10 w-10" />}
          message="Aucun projet pour l'instant"
          description="Créez votre premier projet pour commencer à organiser vos documents."
          action={{
            label: "Créer un projet",
            onClick: () => setShowModal(true),
          }}
        />
      )}

      {/* Drop zone statique */}
      <section className="mt-6">
        <div
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors",
            drop.isDragOver
              ? "border-[#FFC300] bg-[#FFC300]/5"
              : "border-[hsl(var(--border))]",
          )}
        >
          <Upload
            className={cn(
              "h-8 w-8 text-muted-foreground",
              drop.isDragOver && "text-[#FFC300] animate-bounce",
            )}
          />
          <p className="text-sm text-muted-foreground">
            Glissez-déposez un dossier pour créer un projet
          </p>
          <p className="text-xs text-muted-foreground">
            Le projet portera le nom du dossier et ses fichiers seront importés
            automatiquement
          </p>
        </div>
      </section>

      {/* Overlay pleine page pendant le drag */}
      {drop.isDragOver && (
        <div className="pointer-events-none fixed inset-0 z-40 bg-[#FFC300]/5" />
      )}

      {showModal && <CreateProjectModal onClose={() => setShowModal(false)} />}
    </main>
  );
}
