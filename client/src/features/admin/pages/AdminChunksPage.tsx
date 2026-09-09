import { Database } from "lucide-react";
import { useState } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/components/feedback/LoadingScreen";
// eslint-disable-next-line no-restricted-imports -- assumed cross-feature import; the Result<T> spec (docs/specs/service-result-error.md) kept it OUT on 2026-09-01 too. Moving this hook down to shared code, or injecting it from the route, is its own spec
import { useProjects } from "@/features/projects";
import { AdminDashboard } from "../components/AdminDashboard";
import { useAdminStore } from "../stores/store";

export function AdminChunksPage() {
  const { data: projectList, isPending, error, refetch } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  if (isPending) return <LoadingScreen />;

  const projects = projectList?.projects ?? [];

  return (
    <main className="mx-auto max-w-7xl space-y-6 p-4 md:p-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FFC300]/15">
            <Database className="h-5 w-5 text-[#FFC300]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
              Admin RAG
            </h1>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Inspection et analyse des chunks indexés
            </p>
          </div>
        </div>

        <select
          value={selectedProjectId}
          onChange={(e) => {
            useAdminStore.getState().reset();
            setSelectedProjectId(e.target.value);
          }}
          className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
        >
          <option value="">Sélectionner un projet...</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </header>

      {error && <ErrorMessage error={error} onRetry={() => void refetch()} />}

      {selectedProjectId ? (
        <AdminDashboard key={selectedProjectId} projectId={selectedProjectId} />
      ) : (
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-12 text-center">
          <Database className="mx-auto mb-3 h-8 w-8 text-[hsl(var(--muted-foreground))]" />
          <p className="text-sm text-[hsl(var(--muted-foreground))]">
            Sélectionnez un projet pour inspecter ses chunks.
          </p>
        </div>
      )}
    </main>
  );
}
