import { LayoutGrid, List } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProjectsViewStore } from "../stores/projectsViewStore";

export function ViewToggle() {
  const viewMode = useProjectsViewStore((s) => s.viewMode);
  const setViewMode = useProjectsViewStore((s) => s.setViewMode);

  return (
    <div className="flex rounded-md border border-[hsl(var(--border))]">
      <button
        type="button"
        onClick={() => setViewMode("grid")}
        className={cn(
          "rounded-l-md p-2 transition-colors",
          viewMode === "grid"
            ? "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]"
            : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
        )}
        aria-label="Vue grille"
        aria-pressed={viewMode === "grid"}
      >
        <LayoutGrid className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => setViewMode("list")}
        className={cn(
          "rounded-r-md p-2 transition-colors",
          viewMode === "list"
            ? "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]"
            : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]",
        )}
        aria-label="Vue liste"
        aria-pressed={viewMode === "list"}
      >
        <List className="h-4 w-4" />
      </button>
    </div>
  );
}
