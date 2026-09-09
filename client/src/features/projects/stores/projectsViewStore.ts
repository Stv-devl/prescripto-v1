import { create } from "zustand";
import { persist } from "zustand/middleware";
import { registerSessionReset } from "@/lib/store/sessionReset";

type ViewMode = "grid" | "list";
type SortBy = "created_at" | "name" | "document_count";
type SortDirection = "asc" | "desc";

interface ProjectsViewState {
  viewMode: ViewMode;
  searchQuery: string;
  phaseFilter: string | null;
  statusFilter: string | null;
  sortBy: SortBy;
  sortDirection: SortDirection;
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setPhaseFilter: (phase: string | null) => void;
  setStatusFilter: (status: string | null) => void;
  setSortBy: (sortBy: SortBy) => void;
  setSortDirection: (direction: SortDirection) => void;
  resetFilters: () => void;
}

/**
 * Stores user preferences for the projects page view (persisted to localStorage).
 */
export const useProjectsViewStore = create<ProjectsViewState>()(
  persist(
    (set) => ({
      viewMode: "grid",
      searchQuery: "",
      phaseFilter: null,
      statusFilter: "active",
      sortBy: "created_at",
      sortDirection: "desc",
      setViewMode: (viewMode) => set({ viewMode }),
      setSearchQuery: (searchQuery) => set({ searchQuery }),
      setPhaseFilter: (phase) =>
        set((state) => ({
          phaseFilter: state.phaseFilter === phase ? null : phase,
        })),
      setStatusFilter: (status) =>
        set((state) => ({
          statusFilter: state.statusFilter === status ? null : status,
        })),
      setSortBy: (sortBy) => set({ sortBy }),
      setSortDirection: (sortDirection) => set({ sortDirection }),
      resetFilters: () =>
        set({
          searchQuery: "",
          phaseFilter: null,
          statusFilter: "active",
          sortBy: "created_at",
          sortDirection: "desc",
        }),
    }),
    {
      name: "prescripto-projects-view",
      partialize: (state) => ({ viewMode: state.viewMode }),
    },
  ),
);

registerSessionReset(() => useProjectsViewStore.getState().resetFilters());
