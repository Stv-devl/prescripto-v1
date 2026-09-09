import { useParams } from "react-router-dom";

/**
 * Returns a required route parameter as a non-nullable string.
 * Throws if the parameter is missing (should not happen with correct routing).
 */
export function useRequiredParam(name: string): string {
  const params = useParams();
  const value = params[name];
  if (!value) {
    throw new Error(`Missing required route parameter: ${name}`);
  }
  return value;
}
