import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";

interface ErrorMessageProps {
  error: Error | null;
  className?: string;
  /** Compact form for a narrow container — text only, no block chrome. */
  inline?: boolean;
  /**
   * Renders a retry control. Off by default, and omitted where replaying makes
   * no sense — a failed query is otherwise a dead end, since
   * `refetchOnWindowFocus` is disabled.
   */
  onRetry?: () => void;
}

const BLOCK =
  "rounded-lg border border-[hsl(var(--destructive))]/30 bg-[hsl(var(--destructive))]/10 p-4 text-sm text-[hsl(var(--destructive))]";
const INLINE = "text-xs text-[hsl(var(--destructive))]";
const RETRY =
  "mt-2 rounded-md border border-current px-2 py-1 text-xs font-medium hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current";

/**
 * Displays the French copy for a failed operation, with an optional retry.
 *
 * The prop stays an `Error` because React Query hands one down, and `unwrap`
 * throws a `ServiceFailure`, which is one — the code travels inside it.
 */
export function ErrorMessage({
  error,
  className,
  inline = false,
  onRetry,
}: ErrorMessageProps) {
  if (!error) return null;

  return (
    <div role="alert" className={className ?? (inline ? INLINE : BLOCK)}>
      {userMessageFor(toServiceError(error).code)}
      {onRetry && (
        <div>
          <button type="button" onClick={onRetry} className={RETRY}>
            Réessayer
          </button>
        </div>
      )}
    </div>
  );
}
