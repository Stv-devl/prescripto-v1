import { FaqSection } from "../components/FaqSection";
import { FeaturesSection } from "../components/FeaturesSection";
import { FinalCtaSection } from "../components/FinalCtaSection";
import { HeroSection } from "../components/HeroSection";
import { PricingSection } from "../components/PricingSection";
import { StatsSection } from "../components/StatsSection";
import { TestimonialsSection } from "../components/TestimonialsSection";

/**
 * Landing page component.
 * Orchestrates all landing page sections.
 */
export function LandingPage(): React.ReactElement {
  return (
    <main className="flex flex-col">
      <HeroSection />
      <FeaturesSection />
      <StatsSection />
      <TestimonialsSection />
      <PricingSection />
      <FaqSection />
      <FinalCtaSection />
    </main>
  );
}
