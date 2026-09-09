import { useMemo } from "react";
import { useProjectsViewStore } from "../stores/projectsViewStore";
import type { Project } from "../types/types";

/**
 * Filters, sorts, and partitions projects based on the view store state.
 * Returns filtered list, favorites, and non-favorites.
 */
export function useFilteredProjects(allProjects: Project[]) {
  const searchQuery = useProjectsViewStore((s) => s.searchQuery);
  const phaseFilter = useProjectsViewStore((s) => s.phaseFilter);
  const statusFilter = useProjectsViewStore((s) => s.statusFilter);
  const sortBy = useProjectsViewStore((s) => s.sortBy);
  const sortDirection = useProjectsViewStore((s) => s.sortDirection);

  const filtered = useMemo((): Project[] => {
    let result = allProjects;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.client.toLowerCase().includes(q),
      );
    }

    if (phaseFilter) {
      result = result.filter((p) => p.phase === phaseFilter);
    }

    if (statusFilter) {
      result = result.filter((p) => p.status === statusFilter);
    }

    const sorted = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortBy === "name") {
        cmp = a.name.localeCompare(b.name, "fr");
      } else if (sortBy === "document_count") {
        cmp = a.document_count - b.document_count;
      } else {
        cmp =
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });

    return sorted;
  }, [allProjects, searchQuery, phaseFilter, statusFilter, sortBy, sortDirection]);

  const favorites = useMemo(
    () => filtered.filter((p) => p.is_favorite),
    [filtered],
  );

  const nonFavorites = useMemo(
    () => filtered.filter((p) => !p.is_favorite),
    [filtered],
  );

  return { filtered, favorites, nonFavorites } as const;
}
