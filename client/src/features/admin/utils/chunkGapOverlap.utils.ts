import type { ChunkListItem } from "../types/types";

/** True when two chunks are not contiguous — a position or page jump greater than 1. */
export function hasGap(current: ChunkListItem, previous: ChunkListItem): boolean {
  return current.position - previous.position > 1 || current.page - previous.page > 1;
}

/**
 * Longest suffix of `textA` that is also a prefix of `textB`, considering only
 * candidates of at least 20 characters and searching within `maxCheck`
 * characters from each end. Empty string when no such overlap exists.
 */
export function findOverlap(textA: string, textB: string, maxCheck: number = 400): string {
  const endA = textA.slice(-maxCheck);
  const startB = textB.slice(0, maxCheck);
  let best = "";
  for (let len = 20; len <= Math.min(endA.length, startB.length); len++) {
    const candidate = endA.slice(-len);
    if (startB.startsWith(candidate)) {
      best = candidate;
    }
  }
  return best;
}
