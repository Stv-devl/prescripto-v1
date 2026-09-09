import { Link } from "react-router-dom";

/**
 * Public footer for unauthenticated pages.
 * Displays logo, navigation links, and legal links.
 */
export function PublicFooter(): React.ReactElement {
  return (
    <footer className="border-t border-[#F5F5F5]/10 bg-[#1C1C1C]">
      <div className="container px-4 py-6 sm:py-8">
        {/* Top Row */}
        <div className="flex flex-col items-start gap-4 sm:gap-6 md:flex-row md:items-center">
          {/* Logo - Left */}
          <Link
            to="/"
            className="hidden md:flex items-center space-x-2 group md:flex-1"
          >
            <img
              src="/prescripto-logo.webp"
              alt="Prescripto"
              width={32}
              height={32}
              loading="lazy"
              decoding="async"
              className="h-8 w-8 rounded-lg"
            />
            <span className="font-bold text-lg text-[#FFC300]">Prescripto</span>
          </Link>

          {/* Links - Center */}
          <div className="w-full flex flex-wrap items-center justify-evenly md:gap-6 md:justify-center md:flex-1">
            <a
              href="/#features-section"
              className="text-sm text-[#F5F5F5]/60 hover:text-[#FFC300] transition-colors"
            >
              Fonctionnalités
            </a>
            <a
              href="/#pricing-section"
              className="text-sm text-[#F5F5F5]/60 hover:text-[#FFC300] transition-colors"
            >
              Tarifs
            </a>
            <a
              href="mailto:contact@prescripto.fr"
              className="text-sm text-[#F5F5F5]/60 hover:text-[#FFC300] transition-colors"
            >
              Contact
            </a>
          </div>

          {/* Empty space - Right */}
          <div className="hidden md:block md:flex-1" />
        </div>

        {/* Bottom Row */}
        <div className="flex flex-col items-center gap-3 sm:gap-4 mt-5 pt-5 sm:mt-6 sm:pt-6 border-t border-[#F5F5F5]/10 md:flex-row md:justify-between md:items-start">
          {/* Copyright */}
          <p className="text-xs sm:text-sm text-[#F5F5F5]/40">
            &copy; 2026 Prescripto. Tous droits réservés.
          </p>

          {/* Legal Links */}
          <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 md:gap-6">
            <Link
              to="/privacy"
              className="text-xs sm:text-sm text-[#F5F5F5]/40 hover:text-[#FFC300] transition-colors"
            >
              Confidentialité
            </Link>
            <Link
              to="/terms"
              className="text-xs sm:text-sm text-[#F5F5F5]/40 hover:text-[#FFC300] transition-colors"
            >
              Conditions
            </Link>
            <Link
              to="/cookies"
              className="text-xs sm:text-sm text-[#F5F5F5]/40 hover:text-[#FFC300] transition-colors"
            >
              Cookies
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
