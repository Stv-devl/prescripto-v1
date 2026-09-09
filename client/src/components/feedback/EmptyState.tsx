import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";

interface EmptyStateProps {
  message: string;
  description?: string;
  icon?: ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Placeholder displayed when a list or section has no content.
 * Supports an optional icon, description, and call-to-action button.
 */
export function EmptyState({ message, description, icon, action }: EmptyStateProps) {
  return (
    <section className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="mb-3 text-[hsl(var(--muted-foreground))]">{icon}</div>
      )}
      <p className="text-muted-foreground">{message}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[hsl(var(--muted-foreground))]/70">
          {description}
        </p>
      )}
      {action && (
        <Button className="mt-4" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </section>
  );
}
