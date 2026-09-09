/**
 * Reference-counts a boolean DOM effect shared by callers that can overlap —
 * e.g. two dialogs stacked on top of each other. `apply` runs only on the
 * 0→1 edge and `revert` only on the 1→0 edge, so a second acquirer's release
 * never undoes an effect a first acquirer still needs.
 */
const depthByTarget = new WeakMap<object, number>();

export function acquire(target: object, apply: () => void): void {
  const depth = depthByTarget.get(target) ?? 0;
  if (depth === 0) apply();
  depthByTarget.set(target, depth + 1);
}

export function release(target: object, revert: () => void): void {
  const depth = depthByTarget.get(target) ?? 0;
  const next = depth - 1;
  if (next <= 0) {
    depthByTarget.delete(target);
    revert();
  } else {
    depthByTarget.set(target, next);
  }
}
