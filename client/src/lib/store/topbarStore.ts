import { create } from "zustand";
import { registerSessionReset } from "./sessionReset";

interface TopbarState {
  title: string | null;
  setTitle: (title: string | null) => void;
  reset: () => void;
}

/**
 * Store for displaying a contextual title in the Topbar.
 */
export const useTopbarStore = create<TopbarState>((set) => ({
  title: null,
  setTitle: (title) => set({ title }),
  reset: () => set({ title: null }),
}));

registerSessionReset(() => useTopbarStore.getState().reset());

