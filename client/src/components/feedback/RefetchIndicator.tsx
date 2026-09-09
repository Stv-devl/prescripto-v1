import { LoadingSpinner } from "./LoadingSpinner";

/**
 * Small spinner positioned in the top-right corner to indicate a background refetch.
 * Place inside a `position: relative` container.
 */
export function RefetchIndicator() {
  return (
    <div className="absolute right-2 top-2">
      <LoadingSpinner size="sm" className="text-gray-400" />
    </div>
  );
}
