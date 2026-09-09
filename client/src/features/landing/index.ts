/**
 * Landing Feature - Public API
 *
 * This module exports all public interfaces of the Landing feature.
 * Import from @/features/landing for all landing-related functionality.
 */

// ============================================================================
// TYPES
// ============================================================================

export type {
  Feature,
  Step,
  Stat,
  Testimonial,
  LandingPricingPlan,
} from "./types/types";

// ============================================================================
// PAGES
// ============================================================================

export { LandingPage } from "./pages/LandingPage";
