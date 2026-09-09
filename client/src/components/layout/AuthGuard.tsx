import { Navigate, Outlet } from "react-router-dom";
import { LoadingScreen } from "@/components/feedback/LoadingScreen";
import { useAuthStore } from "@/lib/store/authStore";
import { useSession } from "@/providers/SessionProvider";

export function AuthGuard() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isHydrated = useAuthStore((s) => s.isHydrated);
  const { isPending } = useSession();

  if (!isHydrated || (isAuthenticated && isPending)) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
