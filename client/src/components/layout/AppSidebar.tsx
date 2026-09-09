import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Database,
  FolderOpen,
  LogOut,
  Settings,
  X,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/lib/store/authStore";
import { useSidebarStore } from "@/lib/store/sidebarStore";
import { useThemeStore } from "@/lib/store/themeStore";
import { cn } from "@/lib/utils";
import { useSession } from "@/providers/SessionProvider";

const LOGO_LIGHT = "/prescripto-logo-dark.webp";
const LOGO_DARK = "/prescripto-logo.webp";

const NAV_ITEMS = [
  { to: "/projects", label: "Projets", icon: FolderOpen },
  { to: "/abonnement", label: "Abonnement", icon: CreditCard },
  { to: "/tutoriel", label: "Tutoriel", icon: BookOpen },
] as const;

/**
 * Application sidebar — collapsible on desktop, overlay on mobile.
 */
export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useSession();
  const user = useAuthStore((s) => s.user);
  const { isOpen, isCollapsed, closeSidebar, setCollapsed } = useSidebarStore();
  const { theme } = useThemeStore();
  const logoSrc = theme === "dark" ? LOGO_DARK : LOGO_LIGHT;

  function handleNavClick(): void {
    if (window.innerWidth < 768) closeSidebar();
  }

  function handleLogout(): void {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex h-screen flex-col border-r border-[hsl(var(--border))] bg-[hsl(var(--background))] transition-all duration-300",
        isOpen ? "translate-x-0" : "-translate-x-full",
        "w-64",
        "md:relative md:w-16 md:translate-x-0",
        isCollapsed ? "lg:w-16" : "lg:w-64",
      )}
    >
      {/* Header */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-[hsl(var(--border))] px-4">
        {/* Logo + title — mobile & desktop expanded */}
        <div className="flex items-center gap-2 md:hidden lg:flex">
          {!isCollapsed && (
            <>
              <img
                src={logoSrc}
                alt="Prescripto"
                width={28}
                height={28}
                className="h-7 w-7"
              />
              <span className="text-lg font-bold text-[hsl(var(--primary))]">
                Prescripto
              </span>
            </>
          )}
        </div>

        {/* Logo only — tablet & desktop collapsed */}
        <img
          src={logoSrc}
          alt="Prescripto"
          width={28}
          height={28}
          className={cn(
            "mx-auto h-7 w-7",
            "hidden md:block",
            !isCollapsed && "lg:hidden",
          )}
        />

        {/* Close button mobile */}
        <button
          onClick={closeSidebar}
          aria-label="Fermer le menu"
          className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[hsl(var(--muted))] md:hidden"
        >
          <X className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
        </button>

        {/* Collapse button desktop — only when expanded */}
        {!isCollapsed && (
          <button
            onClick={() => setCollapsed(true)}
            aria-label="Réduire le menu"
            className="hidden h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[hsl(var(--muted))] lg:flex"
          >
            <ChevronLeft className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        )}
      </div>

      {/* Expand button when collapsed */}
      {isCollapsed && (
        <div className="hidden shrink-0 px-2 py-4 lg:block">
          <button
            onClick={() => setCollapsed(false)}
            aria-label="Ouvrir le menu"
            className="mx-auto flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[hsl(var(--muted))]"
          >
            <ChevronRight className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav
        className={cn(
          "flex-1 space-y-1 overflow-y-auto py-4",
          "px-4 md:px-2",
          !isCollapsed && "lg:px-4",
        )}
      >
        {NAV_ITEMS.map((item) => {
          const active = location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={handleNavClick}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                "group relative flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                "gap-3 md:justify-center",
                !isCollapsed && "lg:justify-start lg:gap-3",
                isCollapsed && "lg:justify-center",
                active
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-md"
                  : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
              )}
              aria-current={active ? "page" : undefined}
            >
              <item.icon
                className={cn(
                  "h-5 w-5 shrink-0 transition-colors",
                  active
                    ? "text-[hsl(var(--primary-foreground))]"
                    : "text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]",
                )}
              />
              <span className={cn("md:hidden", !isCollapsed && "lg:inline")}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {/* Admin section — visible only for admin role */}
        {user?.role === "admin" && (
          <>
            <div className="my-2 border-t border-[hsl(var(--border))]" />
            <Link
              to="/admin/chunks"
              onClick={handleNavClick}
              title={isCollapsed ? "Admin RAG" : undefined}
              className={cn(
                "group relative flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                "gap-3 md:justify-center",
                !isCollapsed && "lg:justify-start lg:gap-3",
                isCollapsed && "lg:justify-center",
                location.pathname === "/admin/chunks"
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-md"
                  : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
              )}
              aria-current={
                location.pathname === "/admin/chunks" ? "page" : undefined
              }
            >
              <Database
                className={cn(
                  "h-5 w-5 shrink-0 transition-colors",
                  location.pathname === "/admin/chunks"
                    ? "text-[hsl(var(--primary-foreground))]"
                    : "text-[hsl(var(--muted-foreground))] group-hover:text-[hsl(var(--foreground))]",
                )}
              />
              <span className={cn("md:hidden", !isCollapsed && "lg:inline")}>
                Admin RAG
              </span>
            </Link>
          </>
        )}
      </nav>

      {/* Footer — settings + logout */}
      <div
        className={cn(
          "shrink-0 space-y-1 border-t border-[hsl(var(--border))] py-4",
          "px-4 md:px-2",
          !isCollapsed && "lg:px-4",
        )}
      >
        <Link
          to="/settings"
          onClick={handleNavClick}
          title={isCollapsed ? "Paramètres" : undefined}
          className={cn(
            "group flex w-full items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
            "gap-3 md:justify-center",
            !isCollapsed && "lg:justify-start lg:gap-3",
            isCollapsed && "lg:justify-center",
            "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
          )}
        >
          <Settings className="h-5 w-5 shrink-0 text-[hsl(var(--muted-foreground))] transition-colors group-hover:text-[hsl(var(--foreground))]" />
          <span className={cn("md:hidden", !isCollapsed && "lg:inline")}>
            Paramètres
          </span>
        </Link>
        <button
          onClick={handleLogout}
          title={isCollapsed ? "Se déconnecter" : undefined}
          className={cn(
            "group flex w-full items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
            "gap-3 md:justify-center",
            !isCollapsed && "lg:justify-start lg:gap-3",
            isCollapsed && "lg:justify-center",
            "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]",
          )}
        >
          <LogOut className="h-5 w-5 shrink-0 text-[hsl(var(--muted-foreground))] transition-colors group-hover:text-[hsl(var(--foreground))]" />
          <span className={cn("md:hidden", !isCollapsed && "lg:inline")}>
            Déconnexion
          </span>
        </button>
      </div>
    </aside>
  );
}
