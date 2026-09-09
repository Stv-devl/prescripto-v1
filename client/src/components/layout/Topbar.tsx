import { Menu, Sun, Moon } from "lucide-react";
import { useSidebarStore } from "@/lib/store/sidebarStore";
import { useThemeStore } from "@/lib/store/themeStore";
import { useTopbarStore } from "@/lib/store/topbarStore";

const LOGO_LIGHT = "/prescripto-logo-dark.webp";
const LOGO_DARK = "/prescripto-logo.webp";

/**
 * Application top bar — hamburger (mobile), theme toggle, user actions.
 */
export function Topbar(): React.JSX.Element {
  const { openSidebar } = useSidebarStore();
  const { theme, toggleTheme } = useThemeStore();
  const title = useTopbarStore((s) => s.title);
  const isDark = theme === "dark";
  const logoSrc = isDark ? LOGO_DARK : LOGO_LIGHT;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 md:h-16 md:px-6">
      {/* Left: hamburger + logo (mobile) */}
      <div className="flex items-center gap-2 md:hidden">
        <button
          onClick={openSidebar}
          aria-label="Ouvrir le menu"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[hsl(var(--muted-foreground))] transition-colors hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-1.5">
          <img
            src={logoSrc}
            alt="Prescripto"
            width={28}
            height={28}
            className="h-7 w-7"
          />
          <span className="text-base font-bold text-[hsl(var(--primary))]">
            Prescripto
          </span>
        </div>
      </div>

      {/* Left: title (desktop) */}
      <div className="hidden md:block">
        {title && (
          <h1 className="text-lg font-bold text-[hsl(var(--foreground))]">
            {title}
          </h1>
        )}
      </div>

      {/* Right: theme toggle */}
      <button
        onClick={toggleTheme}
        aria-label={isDark ? "Passer en mode clair" : "Passer en mode sombre"}
        className="group relative flex h-9 w-[4.25rem] items-center rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-1 transition-all duration-300 hover:border-[hsl(var(--primary))] hover:shadow-[0_0_12px_hsl(var(--primary)/0.25)]"
      >
        {/* Sliding pill */}
        <span
          className={`absolute flex h-7 w-7 items-center justify-center rounded-full bg-[hsl(var(--primary))] shadow-md transition-all duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] ${
            isDark ? "left-1" : "left-[calc(100%-1.75rem-0.25rem)]"
          }`}
        >
          <span
            className={`inline-flex transition-transform duration-500 ${isDark ? "rotate-0" : "rotate-[360deg]"}`}
          >
            {isDark ? (
              <Moon className="h-3.5 w-3.5 text-[hsl(var(--primary-foreground))]" />
            ) : (
              <Sun className="h-3.5 w-3.5 text-[hsl(var(--primary-foreground))]" />
            )}
          </span>
        </span>

        {/* Background icons (dimmed) */}
        <span className="flex w-full items-center justify-between px-1.5">
          <Moon
            className={`h-3.5 w-3.5 transition-opacity duration-300 ${isDark ? "opacity-0" : "opacity-25"}`}
          />
          <Sun
            className={`h-3.5 w-3.5 transition-opacity duration-300 ${isDark ? "opacity-25" : "opacity-0"}`}
          />
        </span>
      </button>
    </header>
  );
}
