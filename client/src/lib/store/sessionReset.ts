type SessionResetHandler = () => void;
type SessionWrite = () => void;

/** Runs a write if the session it was opened in still holds, and says if it did. */
export type SessionScope = (write: SessionWrite) => boolean;

const handlers = new Set<SessionResetHandler>();

let epoch = 0;

/**
 * Registers a store reset to run at every session boundary.
 *
 * @param handler - Brings one store back to its initial state.
 */
export function registerSessionReset(handler: SessionResetHandler): void {
  handlers.add(handler);
}

/**
 * Runs every registered reset. Safe to call twice, and on an empty registry.
 */
export function resetSessionState(): void {
  epoch += 1;
  for (const handler of handlers) {
    handler();
  }
}

/**
 * Identifies the session in force — the primitive `beginSessionScope` is built
 * on. Never compare it by hand at a call site: open a scope instead.
 */
export function currentSessionEpoch(): number {
  return epoch;
}

/**
 * Captures the session in force. The executor it returns runs a write only if no
 * session boundary has been crossed since, and reports whether it did.
 *
 * Open it before the first await of the path it protects. Every guarded write is
 * inventoried in `guardedWrites.test.ts`; a new one earns a line there.
 *
 * @returns Runs the write and returns true, or skips it and returns false.
 */
export function beginSessionScope(): SessionScope {
  const openedAt = epoch;

  return (write) => {
    if (epoch !== openedAt) return false;
    write();
    return true;
  };
}

/**
 * How many resets are registered — read by the store registration test.
 */
export function registeredSessionResetCount(): number {
  return handlers.size;
}
