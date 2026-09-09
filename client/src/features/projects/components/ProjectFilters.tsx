import { cn } from "@/lib/utils";
import { useProjectsViewStore } from "../stores/projectsViewStore";

const PHASES = ["ESQ", "APS", "APD", "PRO", "DCE", "EXE", "DOE"] as const;
const STATUSES = [
  { value: "active", label: "Actif" },
  { value: "archived", label: "Archivé" },
] as const;

const SORT_OPTIONS = [
  { value: "created_at:desc", label: "Date (récent)" },
  { value: "created_at:asc", label: "Date (ancien)" },
  { value: "name:asc", label: "Nom (A-Z)" },
  { value: "document_count:desc", label: "Nb documents" },
] as const;

export function ProjectFilters() {
  const phaseFilter = useProjectsViewStore((s) => s.phaseFilter);
  const statusFilter = useProjectsViewStore((s) => s.statusFilter);
  const sortBy = useProjectsViewStore((s) => s.sortBy);
  const sortDirection = useProjectsViewStore((s) => s.sortDirection);
  const setPhaseFilter = useProjectsViewStore((s) => s.setPhaseFilter);
  const setStatusFilter = useProjectsViewStore((s) => s.setStatusFilter);
  const setSortBy = useProjectsViewStore((s) => s.setSortBy);
  const setSortDirection = useProjectsViewStore((s) => s.setSortDirection);

  const currentSort = `${sortBy}:${sortDirection}`;

  function handleSortChange(e: React.ChangeEvent<HTMLSelectElement>): void {
    const [field, dir] = e.target.value.split(":") as [
      "created_at" | "name" | "document_count",
      "asc" | "desc",
    ];
    setSortBy(field);
    setSortDirection(dir);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PHASES.map((phase) => (
        <button
          key={phase}
          type="button"
          onClick={() => setPhaseFilter(phase)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            phaseFilter === phase
              ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]"
              : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
          )}
        >
          {phase}
        </button>
      ))}

      <span className="mx-1 h-5 w-px bg-[hsl(var(--border))]" aria-hidden="true" />

      {STATUSES.map((status) => (
        <button
          key={status.value}
          type="button"
          onClick={() => setStatusFilter(status.value)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            statusFilter === status.value
              ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]"
              : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
          )}
        >
          {status.label}
        </button>
      ))}

      <span className="mx-1 h-5 w-px bg-[hsl(var(--border))]" aria-hidden="true" />

      <select
        value={currentSort}
        onChange={handleSortChange}
        className="h-8 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-2 text-xs text-[hsl(var(--foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]/50"
        aria-label="Trier par"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
