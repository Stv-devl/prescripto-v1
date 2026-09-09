import { Search, X } from "lucide-react";
import { useProjectsViewStore } from "../stores/projectsViewStore";

export function ProjectSearchBar() {
  const searchQuery = useProjectsViewStore((s) => s.searchQuery);
  const setSearchQuery = useProjectsViewStore((s) => s.setSearchQuery);

  return (
    <div className="relative">
      <Search
        className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[hsl(var(--muted-foreground))]"
        aria-hidden="true"
      />
      <input
        type="search"
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="Rechercher un projet..."
        className="h-10 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] pl-9 pr-9 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary))]/50"
      />
      {searchQuery && (
        <button
          type="button"
          onClick={() => setSearchQuery("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          aria-label="Effacer la recherche"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
