import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/user";
import { resetSessionState } from "./sessionReset";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
}

interface AuthActions {
  openSession: (accessToken: string, refreshToken: string) => void;
  renewTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

/**
 * Auth store — manages JWT tokens and user state.
 * Tokens are persisted in localStorage via Zustand persist middleware.
 */
export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isHydrated: false,

      openSession: (accessToken, refreshToken) => {
        resetSessionState();
        set({ user: null, accessToken, refreshToken, isAuthenticated: true });
      },

      renewTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken, isAuthenticated: true });
      },

      setUser: (user) => {
        set({ user });
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
        resetSessionState();
      },
    }),
    {
      name: "prescripto-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.isAuthenticated = !!state.accessToken;
          state.isHydrated = true;
        }
      },
    },
  ),
);
