import { motion } from "framer-motion";
import { Shield, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
/**
 * Hero section of the landing page.
 * Displays the main headline, description, CTAs and dashboard preview.
 * Features animated cloud-like golden blobs drifting over the dark background.
 */
export function HeroSection(): React.ReactElement {
  const scrollToPricing = (): void => {
    const pricingSection = document.getElementById("pricing-section");
    pricingSection?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className="relative pt-20 pb-[60px] overflow-hidden isolate">
      {/* Animated cloud background */}
      <div className="absolute inset-0 -z-10 flex items-center justify-center">
        <img
          src="/hero-clouds.svg"
          alt=""
          className="absolute w-full max-w-[1950px] min-w-[1440px] h-auto animate-clouds-drift landing-hero-mask top-28"
        />
      </div>

      <div className="relative z-10">
        <div className="container px-4">
          <motion.div
            className="text-center space-y-3 md:space-y-8 max-w-4xl mx-auto"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          >
            <div className="inline-flex items-center text-left sm:text-center px-4 py-2 rounded-full bg-[#FFC300]/10 border border-[#FFC300]/20 text-[#FFC300] text-xs md:text-sm font-medium">
              <Shield className="w-4 h-4 mr-2.5" />
              L'IA souveraine pour la maîtrise d'œuvre
            </div>

            <h1 className="text-2xl sm:text-3xl md:text-5xl lg:text-6xl font-bold tracking-tight text-[#F5F5F5]">
              Ne cherchez plus dans vos dossiers,
              <span className="text-[#FFC300]"> interrogez-les.</span>
            </h1>

            <p className="text-sm sm:text-base md:text-lg lg:text-xl text-[#F5F5F5]/60 max-w-2xl mx-auto">
              200 pièces par projet, des milliers de pages. Prescripto les
              ingère, les comprend et répond à vos questions avec le document,
              la page et le passage exact.
            </p>

            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center pt-4">
              <Button
                asChild
                size="lg"
                className="bg-[#FFC300] hover:bg-[#FFD54F] text-[#1C1C1C] font-semibold shadow-lg shadow-[#FFC300]/20"
              >
                <Link to="/signup">
                  Essayer gratuitement
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={scrollToPricing}
                className="border-[#F5F5F5]/20 text-[#F5F5F5] hover:bg-[#F5F5F5]/10"
              >
                Voir les tarifs
              </Button>
            </div>

            <p className="text-sm text-[#F5F5F5]/40">
              Conçu pour les architectes, économistes, BET et maîtres d'œuvre
            </p>
          </motion.div>

          {/* Dashboard Preview */}
          <motion.div
            className="mt-6 md:mt-20 max-w-5xl mx-auto relative z-10"
            initial={{ opacity: 0, y: 100, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
          >
            <div className="relative">
              {/* Glow effect behind the image */}
              <div className="absolute -inset-2 md:-inset-4 bg-gradient-to-r from-[#FFC300]/10 via-[#FFC300]/5 to-[#FFC300]/10 rounded-3xl blur-2xl opacity-60" />

              {/* Card container */}
              <div className="relative bg-[#2B2B2B] rounded-xl md:rounded-2xl border border-[#F5F5F5]/10 shadow-2xl overflow-hidden">
                {/* Browser-like header */}
                <div className="flex items-center gap-2 px-4 py-3 bg-[#1C1C1C]/50 border-b border-[#F5F5F5]/10">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-400" />
                    <div className="w-3 h-3 rounded-full bg-yellow-400" />
                    <div className="w-3 h-3 rounded-full bg-green-400" />
                  </div>
                  <div className="flex-1 flex justify-center">
                    <div className="px-4 py-1 bg-[#1C1C1C]/50 rounded-md text-xs text-[#F5F5F5]/40">
                      www.prescripto.fr
                    </div>
                  </div>
                </div>

                {/* Dashboard image */}
                <img
                  src="/dashboard.webp"
                  alt="Interface Prescripto - GED intelligente pour la construction"
                  className="w-full h-auto"
                  loading="eager"
                  decoding="async"
                  width={1822}
                  height={918}
                />
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
