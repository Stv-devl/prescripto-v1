import { Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { Topbar } from "@/components/layout/Topbar";
import { useSidebarStore } from "@/lib/store/sidebarStore";

/**
 * Main application shell — sidebar + topbar + content area.
 */
export function AppLayout() {
  const { isOpen, closeSidebar } = useSidebarStore();

  return (
    <div className="flex h-screen w-full bg-[hsl(var(--background))]">
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      <AppSidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
