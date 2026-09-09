import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  ArrowRight,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import type { LandingPricingPlan } from "../types/types";

const PRICING_PLANS: LandingPricingPlan[] = [
  {
    id: "solo",
    name: "Solo",
    description: "Pour l'économiste indépendant",
    price: "149,00",
    credits: "500 requêtes IA",
    features: [
      "1 utilisateur",
      "5 projets actifs",
      "500 requêtes IA/mois",
      "PDF, DOCX, XLSX",
    ],
    comingSoon: ["Détection d'incohérences"],
    popular: false,
  },
  {
    id: "equipe",
    name: "Équipe",
    description: "Pour les BET et maîtrises d'oeuvre",
    price: "349,00",
    credits: "2 000 requêtes IA",
    discountPercent: 20,
    features: [
      "5 utilisateurs",
      "20 projets actifs",
      "2 000 requêtes IA/mois",
      "PDF, DOCX, XLSX, DWG",
    ],
    comingSoon: ["Détection d'incohérences", "Génération CCTP assistée"],
    popular: true,
  },
  {
    id: "cabinet",
    name: "Cabinet",
    description: "Pour les cabinets avec prestataires",
    price: "699,00",
    credits: "Requêtes illimitées",
    discountPercent: 50,
    features: [
      "Utilisateurs illimités",
      "Projets illimités",
      "Requêtes illimitées",
      "Tous formats + IFC",
    ],
    comingSoon: ["Détection d'incohérences", "Génération CCTP + API"],
    popular: false,
  },
];

function PlanCard({ plan }: { plan: LandingPricingPlan }): React.ReactElement {
  return (
    <Card
      className={`
        relative flex flex-col transition-all duration-200 bg-[#2B2B2B]
        ${plan.popular ? "border-[#FFC300] border-2 shadow-lg shadow-[#FFC300]/10 md:scale-105" : "border-[#F5F5F5]/10 hover:border-[#FFC300]/40 hover:shadow-md"}
      `}
    >
      {plan.popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <Badge className="bg-[#FFC300] text-[#1C1C1C] shadow-sm flex items-center gap-1 text-xs px-2 py-0.5">
            <TrendingUp className="h-2.5 w-2.5" />
            POPULAIRE
          </Badge>
        </div>
      )}

      <CardContent className="p-4 lg:p-6 flex flex-col h-full">
        <div className="text-center space-y-0.5 mb-4 lg:mb-6">
          <h3 className="text-lg lg:text-xl font-bold text-[#F5F5F5]">
            {plan.name}
          </h3>
          <p className="text-sm text-[#F5F5F5]/60 lg:min-h-10">
            {plan.description}
          </p>
          <div className="flex items-baseline justify-center gap-1">
            <span className="text-3xl lg:text-4xl font-bold text-[#F5F5F5]">
              {plan.price}
            </span>
            <span className="text-[#F5F5F5]/60 text-lg">€</span>
            <span className="text-[#F5F5F5]/60 text-sm">/mois</span>
          </div>
          <p className="text-sm text-[#F5F5F5]/60 leading-tight">
            {plan.credits}/mois
          </p>
          <div className="h-6">
            {plan.discountPercent && (
              <Badge className="bg-green-500 text-white hover:bg-green-600">
                -{plan.discountPercent}% par requête
              </Badge>
            )}
          </div>
        </div>

        <ul className="space-y-2 lg:space-y-3 flex-1 mb-4 lg:mb-6">
          {plan.features.map((feature) => (
            <li key={feature} className="flex items-center gap-2">
              <div className="shrink-0 text-[#FFC300]">
                <Check className="h-4 w-4" />
              </div>
              <span className="text-sm text-[#F5F5F5]">{feature}</span>
            </li>
          ))}

          {plan.comingSoon?.map((feature) => (
            <li key={feature} className="flex items-center gap-2 opacity-50">
              <div className="shrink-0 text-[#FFC300]">
                <Check className="h-4 w-4" />
              </div>
              <span className="text-sm text-[#F5F5F5] whitespace-nowrap">
                {feature}
              </span>
              <Badge
                variant="outline"
                className="shrink-0 ml-1 text-xs px-1.5 py-0 border-[#FFC300]/40 text-[#FFC300]"
              >
                Bientôt
              </Badge>
            </li>
          ))}
        </ul>

        <Button
          asChild
          className="w-full mt-auto font-semibold text-base bg-[#FFC300] text-[#1C1C1C] hover:bg-[#FFD54F]"
          size="lg"
        >
          <Link to="/signup">S'abonner</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Pricing section displaying subscription plans.
 */
export function PricingSection(): React.ReactElement {
  const [mobileIndex, setMobileIndex] = useState(1);

  const goToPrev = (): void => {
    setMobileIndex((prev) =>
      prev === 0 ? PRICING_PLANS.length - 1 : prev - 1,
    );
  };

  const goToNext = (): void => {
    setMobileIndex((prev) =>
      prev === PRICING_PLANS.length - 1 ? 0 : prev + 1,
    );
  };

  return (
    <section
      id="pricing-section"
      className="relative py-5 md:py-16 overflow-hidden isolate"
    >
      {/* Animated dark cloud background */}
      <div className="absolute inset-0 -z-10 flex items-center justify-center">
        <img
          src="/pricing-clouds.svg"
          alt=""
          className="absolute w-full max-w-[1950px] min-w-[1440px] h-auto animate-clouds-drift landing-hero-mask top-0"
        />
      </div>

      <div className="container px-4 relative z-10">
        <motion.div
          className="text-center space-y-5 md:space-y-12"
          initial={{ opacity: 0, y: 50 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 1, ease: "easeOut" }}
        >
          <div className="space-y-2 md:space-y-4">
            <h2 className="text-xl sm:text-2xl md:text-4xl font-bold text-[#F5F5F5]">
              Commencez gratuitement, évoluez quand vous voulez
            </h2>
            <p className="text-[#F5F5F5]/60 max-w-2xl mx-auto">
              Testez sur un projet. Passez à un abonnement pour votre cabinet.
            </p>
          </div>

          {/* Desktop: 3-column grid */}
          <div className="hidden md:grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {PRICING_PLANS.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>

          {/* Mobile: single card carousel */}
          <div className="md:hidden max-w-sm mx-auto">
            <div className="overflow-hidden pt-4">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.div
                  key={PRICING_PLANS[mobileIndex].id}
                  initial={{ opacity: 0, x: 80 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -80 }}
                  transition={{ duration: 0.25, ease: "easeInOut" }}
                >
                  <PlanCard plan={PRICING_PLANS[mobileIndex]} />
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Chevrons */}
            <div className="flex items-center justify-center gap-6 mt-3 md:mt-5">
              <button
                onClick={goToPrev}
                className="flex items-center justify-center w-10 h-10 rounded-full bg-[#2B2B2B] border-2 border-[#FFC300]/20 shadow-xl cursor-pointer hover:border-[#FFC300] hover:bg-[#FFC300]/5 transition-all duration-300 active:scale-90"
                aria-label="Plan précédent"
              >
                <ChevronLeft className="h-5 w-5 text-[#FFC300]" />
              </button>

              <button
                onClick={goToNext}
                className="flex items-center justify-center w-10 h-10 rounded-full bg-[#2B2B2B] border-2 border-[#FFC300]/20 shadow-xl cursor-pointer hover:border-[#FFC300] hover:bg-[#FFC300]/5 transition-all duration-300 active:scale-90"
                aria-label="Plan suivant"
              >
                <ChevronRight className="h-5 w-5 text-[#FFC300]" />
              </button>
            </div>

            {/* Dots */}
            <div className="flex items-center justify-center gap-2 mt-3">
              {PRICING_PLANS.map((plan, index) => (
                <button
                  key={plan.id}
                  onClick={() => setMobileIndex(index)}
                  className={`w-2.5 h-2.5 rounded-full transition-all duration-300 cursor-pointer ${
                    index === mobileIndex
                      ? "bg-[#FFC300] scale-110"
                      : "bg-[#F5F5F5]/20"
                  }`}
                  aria-label={`Voir le plan ${plan.name}`}
                />
              ))}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 md:gap-4 justify-center items-center">
            <Button
              asChild
              size="sm"
              variant="outline"
              className="border-[#FFC300] text-[#FFC300] hover:bg-[#FFC300]/10 md:size-default text-sm"
            >
              <Link to="/signup">
                Essayer gratuitement (1 projet offert)
                <ArrowRight className="ml-1 md:ml-2 h-3.5 w-3.5 md:h-4 md:w-4" />
              </Link>
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
