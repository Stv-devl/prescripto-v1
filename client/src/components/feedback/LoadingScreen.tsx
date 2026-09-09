import { LoadingSpinner } from "./LoadingSpinner";

/**
 * Full-page centered spinner used during initial page loads.
 */
export function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}
