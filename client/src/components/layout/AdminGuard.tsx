import { Navigate, Outlet } from "react-router-dom";
import { LoadingScreen } from "@/components/feedback/LoadingScreen";
import { useAuthStore } from "@/lib/store/authStore";
import { useSession } from "@/providers/SessionProvider";

/**
 * Keeps the chunk console out of a non-operator's way.
 *
 * A convenience, never a barrier: the role comes from a store fed by
 * `/auth/me`, so any visitor can set it in their own browser. The server-side
 * barrier is `get_admin_user`. `isPending` is read because `user` is not
 * persisted — on a reload it is null until `/auth/me` answers, and reading the
 * role first would eject the operator on every refresh. It is paired with
 * `isAuthenticated` because the session query is disabled when that is false,
 * and a disabled query stays pending forever.
 */
export function AdminGuard(): React.JSX.Element {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { isPending } = useSession();

  if (isAuthenticated && isPending) {
    return <LoadingScreen />;
  }

  if (user?.role !== "admin") {
    return <Navigate to="/projects" replace />;
  }

  return <Outlet />;
}
