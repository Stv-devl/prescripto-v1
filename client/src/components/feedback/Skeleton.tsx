import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
}

const variants = {
  text: "h-4 w-full rounded",
  circular: "h-10 w-10 rounded-full",
  rectangular: "h-24 w-full rounded-md",
};

/**
 * Animated placeholder shimmer for content that is still loading.
 * Supports `text`, `circular`, and `rectangular` variants.
 */
export function Skeleton({ className, variant = "text" }: SkeletonProps) {
  return (
    <div
      className={cn("animate-pulse bg-gray-200", variants[variant], className)}
      aria-hidden="true"
    />
  );
}
