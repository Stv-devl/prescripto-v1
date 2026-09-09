import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * Container card with rounded border and shadow. Pair with `CardContent` for standard padding.
 */
export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-lg border border-[#F5F5F5]/10 bg-[#2B2B2B] text-[#F5F5F5] shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6", className)} {...props} />;
}
