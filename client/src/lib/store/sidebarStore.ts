import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SidebarState {
  isOpen: boolean;
  isCollapsed: boolean;
  openSidebar: () => void;
  closeSidebar: () => void;
  toggleSidebar: () => void;
  setCollapsed: (collapsed: boolean) => void;
}

/**
 * Sidebar state store — manages mobile visibility and desktop collapse.
 * Only `isCollapsed` is persisted to localStorage.
 */
export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      isOpen: false,
      isCollapsed: false,
      openSidebar: () => set({ isOpen: true }),
      closeSidebar: () => set({ isOpen: false }),
      toggleSidebar: () => set((s) => ({ isOpen: !s.isOpen })),
      setCollapsed: (collapsed) => set({ isCollapsed: collapsed }),
    }),
    {
      name: "prescripto-sidebar",
      partialize: (state) => ({ isCollapsed: state.isCollapsed }),
    },
  ),
);
