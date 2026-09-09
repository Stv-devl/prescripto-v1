import { type ElementType, isValidElement } from "react";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AdminGuard } from "@/components/layout/AdminGuard";
import { SessionProvider } from "@/providers/SessionProvider";
import { routes } from "./router";

/**
 * Every `path` sitting anywhere below a route whose element is `component`.
 */
function pathsGuardedBy(component: ElementType, list: RouteObject[]): string[] {
  const found: string[] = [];

  const walk = (nodes: RouteObject[], guarded: boolean): void => {
    for (const node of nodes) {
      const inside =
        guarded || (isValidElement(node.element) && node.element.type === component);
      if (inside && node.path !== undefined) {
        found.push(node.path);
      }
      if (node.children !== undefined) {
        walk(node.children, inside);
      }
    }
  };

  walk(list, false);
  return found;
}

describe("route wiring", () => {
  it("puts the admin path behind the role guard, and nothing else", () => {
    expect(pathsGuardedBy(AdminGuard, routes).sort()).toEqual(["/admin/chunks"]);
  });

  it("keeps the admin path inside the authenticated branch", () => {
    // Order matters: the role guard reads a user that SessionProvider fetches
    // and AuthGuard waits for. Hoisted above them, it would decide on a null.
    // The anchor is SessionProvider because it is what the route element *is* —
    // AuthGuard is its child, the two are written together at router.tsx:93.
    expect(pathsGuardedBy(SessionProvider, routes)).toEqual(
      expect.arrayContaining(["/admin/chunks"]),
    );
  });
});
