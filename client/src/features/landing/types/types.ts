/**
 * Types for the Landing feature
 * Pure TypeScript types (framework-agnostic)
 */
import type { LucideIcon } from "lucide-react";

// ============================================================================
// FEATURE SECTION
// ============================================================================

/** Feature card displayed in the features grid */
export interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
  comingSoon?: boolean;
}

// ============================================================================
// HOW IT WORKS SECTION
// ============================================================================

/** Step in the "how it works" process */
export interface Step {
  number: number;
  title: string;
  description: string;
}

// ============================================================================
// STATS SECTION
// ============================================================================

/** Statistic displayed in the stats grid */
export interface Stat {
  value: string;
  label: string;
}

// ============================================================================
// TESTIMONIALS SECTION
// ============================================================================

/** Customer testimonial */
export interface Testimonial {
  name: string;
  role: string;
  quote: string;
  image: string;
  rating: number;
}

// ============================================================================
// PRICING SECTION
// ============================================================================

/** Pricing plan card for landing page */
export interface LandingPricingPlan {
  id: string;
  name: string;
  description: string;
  price: string;
  credits: string;
  features: string[];
  comingSoon?: string[];
  popular: boolean;
  discountPercent?: number;
}

// ============================================================================
// FAQ SECTION
// ============================================================================

/** FAQ item for accordion */
export interface FaqItem {
  question: string;
  answer: string;
}
