import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "dark" | "light";

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
}

/**
 * Applies the given theme to the DOM by toggling the `.light` class
 * on `<html>` with a 500ms transition.
 */
export function applyThemeToDOM(theme: Theme): void {
  const root = document.documentElement;
  root.classList.add("theme-transitioning");
  root.classList.toggle("light", theme === "light");
  setTimeout(() => {
    root.classList.remove("theme-transitioning");
  }, 500);
}

/**
 * Theme store — manages dark/light mode with localStorage persistence.
 * Applies `.light` class to `<html>` and triggers a smooth 500ms transition.
 */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      toggleTheme: () => {
        const next = get().theme === "dark" ? "light" : "dark";
        applyThemeToDOM(next);
        set({ theme: next });
      },
    }),
    {
      name: "prescripto-theme",
      onRehydrateStorage: () => (state) => {
        if (state?.theme === "light") {
          document.documentElement.classList.add("light");
        }
      },
    },
  ),
);
