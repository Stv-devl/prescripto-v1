import { create } from "zustand";
import { registerSessionReset } from "@/lib/store/sessionReset";

interface SelectionState {
  selectedIds: Set<string>;
  toggle: (id: string) => void;
  toggleAll: (allIds: string[]) => void;
  clear: () => void;
  isSelected: (id: string) => boolean;
  isAllSelected: (allIds: string[]) => boolean;
  isPartiallySelected: (allIds: string[]) => boolean;
  count: () => number;
}

/**
 * Tracks multi-selection of documents for batch actions.
 * Only tracks document IDs, not folder IDs.
 */
export const useSelectionStore = create<SelectionState>((set, get) => ({
  selectedIds: new Set<string>(),

  toggle: (id) =>
    set((state) => {
      const next = new Set(state.selectedIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return { selectedIds: next };
    }),

  toggleAll: (allIds) =>
    set((state) => {
      const allSelected =
        allIds.length > 0 && allIds.every((id) => state.selectedIds.has(id));
      if (allSelected) {
        return { selectedIds: new Set<string>() };
      }
      return { selectedIds: new Set(allIds) };
    }),

  clear: () => set({ selectedIds: new Set<string>() }),

  isSelected: (id) => get().selectedIds.has(id),

  isAllSelected: (allIds) =>
    allIds.length > 0 && allIds.every((id) => get().selectedIds.has(id)),

  isPartiallySelected: (allIds) => {
    const selected = get().selectedIds;
    return (
      allIds.some((id) => selected.has(id)) &&
      !allIds.every((id) => selected.has(id))
    );
  },

  count: () => get().selectedIds.size,
}));

registerSessionReset(() => useSelectionStore.getState().clear());
