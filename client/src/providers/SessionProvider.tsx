import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import * as authService from "@/features/auth/services/auth.service";
import { unwrap } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { beginSessionScope } from "@/lib/store/sessionReset";

interface SessionValue {
  /** True while the identity of an authenticated session is still loading. */
  isPending: boolean;
  /** Clears the tokens, every feature store, and the query cache. */
  logout: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/**
 * Owns the session: the `/auth/me` query and the logout fan-out.
 *
 * Mounted around the guarded branch in `routes/router.tsx`, never above the
 * router: the query must not run on the public routes.
 */
export function SessionProvider({
  children,
}: {
  children: ReactNode;
}): React.JSX.Element {
  const queryClient = useQueryClient();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const setUser = useAuthStore((s) => s.setUser);
  const clearSession = useAuthStore((s) => s.logout);

  const { isPending } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const inSession = beginSessionScope();
      const user = unwrap(await authService.getMe());
      inSession(() => setUser(user));
      return user;
    },
    enabled: isAuthenticated,
    staleTime: 10 * 60 * 1000,
  });

  const logout = useCallback((): void => {
    clearSession();
    queryClient.clear();
  }, [clearSession, queryClient]);

  const value = useMemo(() => ({ isPending, logout }), [isPending, logout]);

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

/** Reads the session. Throws when used outside `SessionProvider`. */
export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (value === null) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return value;
}
