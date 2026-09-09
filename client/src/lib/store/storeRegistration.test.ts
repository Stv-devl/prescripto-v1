import { describe, expect, it } from "vitest";

import { registeredSessionResetCount } from "./sessionReset";

// Eager, so every store module is evaluated and its registration line runs.
// No vi.resetModules() anywhere in this file: a second evaluation would create
// fresh closures and double the count.
const storeModules: Record<string, unknown> = import.meta.glob(
  [
    "/src/lib/store/*.ts",
    "/src/stores/*.ts",
    "/src/features/*/stores/*.ts",
    "/src/features/*/*Store.ts",
    "!/src/**/*.test.ts",
  ],
  { eager: true },
);

/**
 * Stores that deliberately survive a session boundary, each with its reason.
 * A new store must either register a reset or earn a line here.
 */
const NOT_SESSION_SCOPED: Record<string, string> = {
  "/src/lib/store/authStore.ts":
    "owns the session boundary — it clears its own tokens and triggers the others",
  "/src/lib/store/sessionReset.ts": "the registry itself, not a store",
  "/src/lib/store/themeStore.ts":
    "device preference — the chosen theme belongs to this machine, not to a tenant",
  "/src/lib/store/sidebarStore.ts":
    "device preference — the collapsed sidebar is persisted per device",
};

describe("store registration", () => {
  it("registers a reset for every store on disk that is not explicitly exempt", () => {
    const paths = Object.keys(storeModules);
    const exempt = paths.filter((path) => path in NOT_SESSION_SCOPED);

    expect(paths.length - exempt.length).toBe(registeredSessionResetCount());
  });

  it("keeps its exempt list free of stores that no longer exist", () => {
    const paths = Object.keys(storeModules);

    for (const path of Object.keys(NOT_SESSION_SCOPED)) {
      expect(paths).toContain(path);
    }
  });
});
