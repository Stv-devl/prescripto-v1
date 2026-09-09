import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

interface LegalLayoutProps {
  title: string;
  subtitle: string;
  updatedAt: string;
  children: React.ReactNode;
}

/**
 * Shared layout for legal pages (privacy, terms, cookies).
 * Title + metadata sticky on left, content scrollable on right.
 */
export function LegalLayout({
  title,
  subtitle,
  updatedAt,
  children,
}: LegalLayoutProps): React.ReactElement {
  return (
    <main className="min-h-screen bg-[#1C1C1C] py-10 md:py-20">
      <div className="w-full max-w-[1950px] mx-auto px-6 md:px-16 lg:px-24">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm text-[#F5F5F5]/50 hover:text-[#FFC300] transition-colors mb-10 md:mb-16"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour à l'accueil
        </Link>

        <div className="flex flex-col md:flex-row md:gap-16 lg:gap-24 xl:gap-32">
          {/* Left — Title block (sticky on desktop) */}
          <header className="md:w-2/5 lg:w-1/3 shrink-0 mb-10 md:mb-0 md:sticky md:top-24 md:self-start space-y-4">
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-[#F5F5F5] leading-tight">
              {title}
            </h1>
            <p className="text-[#F5F5F5]/50 text-sm md:text-base leading-relaxed max-w-sm">
              {subtitle}
            </p>
            <p className="text-xs text-[#F5F5F5]/30 pt-2 border-t border-[#F5F5F5]/10 inline-block">
              Mis à jour le {updatedAt}
            </p>
          </header>

          {/* Right — Content sections */}
          <article className="md:w-3/5 lg:w-2/3 space-y-10 text-[#F5F5F5]/65 text-sm md:text-base leading-relaxed">
            {children}
          </article>
        </div>
      </div>
    </main>
  );
}
