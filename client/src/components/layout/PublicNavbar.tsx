import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";

/**
 * Public navigation bar for unauthenticated pages.
 * Displays logo, login/signup links. Buttons always visible (no hamburger).
 */
export function PublicNavbar(): React.ReactElement {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#F5F5F5]/10 bg-[#1C1C1C]/95 backdrop-blur supports-backdrop-filter:bg-[#1C1C1C]/60">
      <div className="container flex h-14 md:h-16 items-center justify-between px-3 md:px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center space-x-1.5 md:space-x-2">
          <img
            src="/prescripto-logo.webp"
            alt="Prescripto"
            width={32}
            height={32}
            loading="eager"
            decoding="async"
            className="h-8 w-8 rounded-lg"
          />
          <span className="text-base md:text-xl font-bold text-[#FFC300]">
            Prescripto
          </span>
        </Link>

        {/* Navigation - always visible */}
        <nav className="flex items-center space-x-2 md:space-x-6">
          <Link
            to="/login"
            className="text-sm font-medium text-[#F5F5F5]/60 hover:text-[#FFC300] transition-colors"
          >
            Connexion
          </Link>
          <Button
            asChild
            size="sm"
            className="bg-transparent hover:bg-[#FFC300]/10 text-[#FFC300] font-semibold text-sm h-7 md:h-9 px-2.5 md:px-4 border border-[#FFC300]"
          >
            <Link to="/signup">Commencer</Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}
