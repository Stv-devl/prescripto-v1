import { beforeEach, describe, expect, it, vi } from "vitest";

type Registry = typeof import("./sessionReset");

let registry: Registry;

// The registry is module state with no unregister, so each case takes a fresh
// module instance rather than inheriting the handlers of the previous one.
beforeEach(async () => {
  vi.resetModules();
  registry = await import("./sessionReset");
});

describe("session reset registry", () => {
  it("runs every registered reset, not only the first", () => {
    const ran: string[] = [];
    registry.registerSessionReset(() => ran.push("first"));
    registry.registerSessionReset(() => ran.push("second"));

    registry.resetSessionState();

    expect(ran).toEqual(["first", "second"]);
  });

  it("does not throw when nothing is registered", () => {
    expect(() => {
      registry.resetSessionState();
    }).not.toThrow();
  });

  it("runs a reset registered twice only once", () => {
    const ran: string[] = [];
    const handler = (): void => {
      ran.push("once");
    };
    registry.registerSessionReset(handler);
    registry.registerSessionReset(handler);

    registry.resetSessionState();

    expect(ran).toEqual(["once"]);
  });

  it("counts distinct handlers, so a duplicate does not inflate the total", () => {
    const handler = (): void => {};
    registry.registerSessionReset(handler);
    registry.registerSessionReset(handler);
    registry.registerSessionReset(() => {});

    expect(registry.registeredSessionResetCount()).toBe(2);
  });

  it("moves to a new epoch at every session boundary", () => {
    const before = registry.currentSessionEpoch();

    registry.resetSessionState();

    expect(registry.currentSessionEpoch()).not.toBe(before);
  });

  it("keeps the same epoch when no session boundary is crossed", () => {
    const first = registry.currentSessionEpoch();

    expect(registry.currentSessionEpoch()).toBe(first);
  });

  it("lets a write through when no boundary was crossed, and says it ran", () => {
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();

    const wrote = inSession(() => ran.push("write"));

    expect(ran).toEqual(["write"]);
    expect(wrote).toBe(true);
  });

  it("holds a write back once a boundary was crossed, and says it did not run", () => {
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();

    registry.resetSessionState();
    const wrote = inSession(() => ran.push("write"));

    expect(ran).toEqual([]);
    expect(wrote).toBe(false);
  });

  it("lets both writes through when the same scope still holds", () => {
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();

    const first = inSession(() => ran.push("first"));
    const second = inSession(() => ran.push("second"));

    expect(ran).toEqual(["first", "second"]);
    expect([first, second]).toEqual([true, true]);
  });

  it("holds both writes back once the scope is stale, never re-arming itself", () => {
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();
    registry.resetSessionState();

    const first = inSession(() => ran.push("first"));
    const second = inSession(() => ran.push("second"));

    expect(ran).toEqual([]);
    expect([first, second]).toEqual([false, false]);
  });

  it("takes the session in force, so a scope opened after a boundary still writes", () => {
    registry.resetSessionState();
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();

    const wrote = inSession(() => ran.push("write"));

    expect(ran).toEqual(["write"]);
    expect(wrote).toBe(true);
  });

  it("invalidates only the scopes opened before the boundary", () => {
    const ran: string[] = [];
    const before = registry.beginSessionScope();
    registry.resetSessionState();
    const after = registry.beginSessionScope();

    const staleWrote = before(() => ran.push("stale"));
    const freshWrote = after(() => ran.push("fresh"));

    expect(ran).toEqual(["fresh"]);
    expect(staleWrote).toBe(false);
    expect(freshWrote).toBe(true);
  });

  it("leaves a later scope alone when an earlier one is opened and never used", () => {
    const ran: string[] = [];
    registry.beginSessionScope();
    registry.resetSessionState();
    const inSession = registry.beginSessionScope();

    const wrote = inSession(() => ran.push("write"));

    expect(ran).toEqual(["write"]);
    expect(wrote).toBe(true);
  });

  it("stays usable after a write that threw", () => {
    const ran: string[] = [];
    const inSession = registry.beginSessionScope();

    expect(() => {
      inSession(() => {
        throw new Error("write failed");
      });
    }).toThrow("write failed");

    expect(inSession(() => ran.push("next"))).toBe(true);
    expect(ran).toEqual(["next"]);
  });

  it("keeps its handlers after running, so a second session boundary resets too", () => {
    const ran: string[] = [];
    registry.registerSessionReset(() => ran.push("boundary"));

    registry.resetSessionState();
    registry.resetSessionState();

    expect(ran).toEqual(["boundary", "boundary"]);
  });
});
