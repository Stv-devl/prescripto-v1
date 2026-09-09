import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { NoiseBackground } from "./NoiseBackground";

/**
 * Final CTA section with gradient background.
 */
export function FinalCtaSection(): React.ReactElement {
  return (
    <section className="relative py-5 md:py-20 text-[#1C1C1C] overflow-hidden">
      {/* Background — safety-yellow gradient */}
      <NoiseBackground
        filterId="final-cta-bg"
        rounded="0"
        seed={7890}
        primaryColor="#FFC300"
        secondaryColor="#E6B000"
        noiseColor="rgba(28, 28, 28, 0.15)"
        gradientDirection="90deg"
      />

      <div className="container px-4 text-center space-y-4 md:space-y-8 relative z-10">
        <div className="space-y-2 md:space-y-4">
          <h2 className="text-xl sm:text-2xl md:text-4xl font-bold">
            Prêt à retrouver n'importe quelle info en un clic ?
          </h2>
          <p className="text-[#1C1C1C]/70 max-w-2xl mx-auto">
            Rejoignez les économistes et maîtres d'oeuvre qui ne perdent plus de
            temps à chercher dans leurs dossiers.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 md:gap-4 justify-center">
          <Button
            asChild
            size="lg"
            className="bg-[#1C1C1C] text-[#FFC300] hover:bg-[#2B2B2B]"
          >
            <Link to="/signup">
              Commencer gratuitement
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>

          <Button
            asChild
            variant="outline"
            size="lg"
            className="border-[#1C1C1C] text-[#1C1C1C] bg-[#1C1C1C]/10 hover:bg-[#1C1C1C]/20"
          >
            <Link to="/login">Se connecter</Link>
          </Button>
        </div>

        <p className="text-[#1C1C1C]/50 text-sm">
          1 projet offert&nbsp;-&nbsp;Aucune carte bancaire requise
        </p>
      </div>
    </section>
  );
}
