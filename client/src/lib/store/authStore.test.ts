import { beforeEach, describe, expect, it } from "vitest";

import type { User } from "@/types/user";
import { useAuthStore } from "./authStore";

const AUTH_STORAGE_KEY = "prescripto-auth";

// Captured before any case runs: getState() returns the pristine state including
// the actions, which setState(x, true) would otherwise wipe.
const initialAuth = useAuthStore.getState();

const aUser: User = {
  id: "user-1",
  email: "economiste@vinci.fr",
  role: "member",
  tenant_id: "tenant-a",
  first_name: "Camille",
  last_name: "Roux",
  tenant_name: "Groupe Vinci",
  tenant_plan: "pro",
  created_at: "2026-01-15T09:00:00Z",
};

describe("auth store", () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuth, true);
    localStorage.clear();
  });

  it("authenticates the session when a session is opened", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");

    expect(useAuthStore.getState().accessToken).toBe("access-1");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-1");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("drops the previous user when a session is opened, so the next tenant is never shown the last one", () => {
    useAuthStore.getState().openSession("access-a", "refresh-a");
    useAuthStore.getState().setUser(aUser);

    useAuthStore.getState().openSession("access-b", "refresh-b");

    expect(useAuthStore.getState().user).toBeNull();
  });

  it("keeps the user across a token renewal, which is not a session boundary", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");
    useAuthStore.getState().setUser(aUser);

    useAuthStore.getState().renewTokens("access-2", "refresh-2");

    expect(useAuthStore.getState().user).toEqual(aUser);
  });

  it("swaps both tokens and stays authenticated when tokens are renewed", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");

    useAuthStore.getState().renewTokens("access-2", "refresh-2");

    expect(useAuthStore.getState().accessToken).toBe("access-2");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("drops the user and both tokens on logout", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");
    useAuthStore.getState().setUser(aUser);

    useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it("leaves the hydration flag untouched on logout, so the guard does not redirect mid-rehydration", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");
    const before = useAuthStore.getState().isHydrated;

    useAuthStore.getState().logout();

    expect(useAuthStore.getState().isHydrated).toBe(before);
  });

  it("stores the user without touching the tokens", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");

    useAuthStore.getState().setUser(aUser);

    expect(useAuthStore.getState().user).toEqual(aUser);
    expect(useAuthStore.getState().accessToken).toBe("access-1");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-1");
  });

  it("comes back authenticated from storage when an access token was left there", async () => {
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        state: { accessToken: "stored-access", refreshToken: "stored-refresh" },
        version: 0,
      }),
    );

    await useAuthStore.persist.rehydrate();

    expect(useAuthStore.getState().accessToken).toBe("stored-access");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().isHydrated).toBe(true);
  });

  it("comes back unauthenticated from storage when no access token was left there", async () => {
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        state: { accessToken: null, refreshToken: null },
        version: 0,
      }),
    );

    await useAuthStore.persist.rehydrate();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isHydrated).toBe(true);
  });

  it("writes only the two tokens to storage, never the user", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");
    useAuthStore.getState().setUser(aUser);

    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw ?? "")).toEqual({
      state: { accessToken: "access-1", refreshToken: "refresh-1" },
      version: 0,
    });
  });
});
