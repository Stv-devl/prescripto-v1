import { create } from "zustand";
import { registerSessionReset } from "@/lib/store/sessionReset";
import type { ChunkFilters } from "../types/types";

export type AdminTab =
  | "dashboard"
  | "table"
  | "document"
  | "playground"
  | "sync";

/** The admin mutation that failed, for the banner's French label. */
export type AdminActionKind =
  | "update"
  | "split"
  | "merge"
  | "delete"
  | "rechunk"
  | "enrich";

const DEFAULT_FILTERS: ChunkFilters = {
  page: 1,
  per_page: 50,
  sort_by: "position",
  sort_order: "asc",
};

interface AdminChunksState {
  filters: ChunkFilters;
  selectedChunkId: string | null;
  activeTab: AdminTab;
  selectedDocumentId: string | null;
  /**
   * The failure of an admin mutation, kept here so it outlives the surface that
   * triggered it. A component cannot report what it is no longer mounted to
   * render; the mutation's own `onError` writes here instead. It carries the
   * project it belongs to, so a late failure cannot surface under another one.
   */
  actionFailure: AdminActionFailure | null;
  /**
   * How many mounted surfaces are rendering that failure themselves right now.
   * A count, not a flag: two surfaces claiming at once must both release
   * before the banner speaks again — one releasing must not silence the
   * other's claim.
   */
  actionFailureClaimants: number;
}

interface AdminChunksActions {
  setFilter: <K extends keyof ChunkFilters>(key: K, value: ChunkFilters[K]) => void;
  setFilters: (partial: Partial<ChunkFilters>) => void;
  resetFilters: () => void;
  selectChunk: (id: string | null) => void;
  setActiveTab: (tab: AdminTab) => void;
  setSelectedDocument: (id: string | null) => void;
  reportActionFailure: (error: Error, projectId: string, kind: AdminActionKind) => void;
  clearActionFailure: () => void;
  claimActionFailure: () => void;
  releaseActionFailure: () => void;
  reset: () => void;
}

/** A failed admin action, with the project it was run against. */
export interface AdminActionFailure {
  error: Error;
  projectId: string;
  kind: AdminActionKind;
}

/**
 * Admin chunks store — manages filter state, selected chunk, and active tab.
 */
export const useAdminStore = create<AdminChunksState & AdminChunksActions>()(
  (set) => ({
    filters: { ...DEFAULT_FILTERS },
    selectedChunkId: null,
    activeTab: "dashboard",
    selectedDocumentId: null,
    actionFailure: null,
    actionFailureClaimants: 0,

    setFilter: (key, value) => {
      set((state) => ({
        filters: { ...state.filters, [key]: value, page: key === "page" ? (value as number) : 1 },
      }));
    },

    setFilters: (partial) => {
      set((state) => ({
        filters: { ...state.filters, ...partial, page: partial.page ?? 1 },
      }));
    },

    resetFilters: () => {
      set({ filters: { ...DEFAULT_FILTERS } });
    },

    selectChunk: (id) => {
      set({ selectedChunkId: id });
    },

    setActiveTab: (tab) => {
      set({ activeTab: tab });
    },

    setSelectedDocument: (id) => {
      set({ selectedDocumentId: id });
    },

    reportActionFailure: (error, projectId, kind) => {
      set({ actionFailure: { error, projectId, kind }, actionFailureClaimants: 0 });
    },

    clearActionFailure: () => {
      set({ actionFailure: null, actionFailureClaimants: 0 });
    },

    claimActionFailure: () => {
      set((state) => ({ actionFailureClaimants: state.actionFailureClaimants + 1 }));
    },

    releaseActionFailure: () => {
      set((state) => ({
        actionFailureClaimants: Math.max(0, state.actionFailureClaimants - 1),
      }));
    },

    reset: () => {
      set({
        filters: { ...DEFAULT_FILTERS },
        selectedChunkId: null,
        activeTab: "dashboard",
        selectedDocumentId: null,
        actionFailure: null,
        actionFailureClaimants: 0,
      });
    },
  }),
);

registerSessionReset(() => useAdminStore.getState().reset());
