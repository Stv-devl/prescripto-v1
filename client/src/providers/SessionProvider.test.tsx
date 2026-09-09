import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import * as authService from "@/features/auth/services/auth.service";
import { usePendingFolderUploadStore } from "@/features/projects/stores/pendingFolderUploadStore";
import { useSelectionStore } from "@/features/projects/stores/selectionStore";
import { ok } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { useTopbarStore } from "@/lib/store/topbarStore";
import { createQueryClientWrapper } from "@/test/utils";
import type { User } from "@/types/user";
import { SessionProvider, useSession } from "./SessionProvider";

vi.mock("@/features/auth/services/auth.service");

const tenantAUser: User = {
  id: "user-a",
  email: "economiste@vinci.fr",
  role: "member",
  tenant_id: "tenant-a",
  first_name: "Camille",
  last_name: "Roux",
  tenant_name: "Groupe Vinci",
  tenant_plan: "pro",
  created_at: "2026-01-15T09:00:00Z",
};

const initialAuth = useAuthStore.getState();
const initialPendingFolderUpload = usePendingFolderUploadStore.getState();
const initialSelection = useSelectionStore.getState();
const initialTopbar = useTopbarStore.getState();

/** Wraps the Query client wrapper with the provider under test. */
function sessionWrapper() {
  const { wrapper: QueryWrapper, queryClient } = createQueryClientWrapper();

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryWrapper>
        <SessionProvider>{children}</SessionProvider>
      </QueryWrapper>
    );
  }

  return { wrapper, queryClient };
}

function authenticate(): void {
  useAuthStore.setState(
    {
      ...initialAuth,
      accessToken: "access-a",
      refreshToken: "refresh-a",
      isAuthenticated: true,
    },
    true,
  );
}

describe("the session logout", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthStore.setState(initialAuth, true);
    usePendingFolderUploadStore.setState(initialPendingFolderUpload, true);
    useSelectionStore.setState(initialSelection, true);
    useTopbarStore.setState(initialTopbar, true);
  });

  it("clears the feature stores, not only the tokens", () => {
    usePendingFolderUploadStore.getState().setPending({
      folderName: "Groupe Vinci — Lot 03",
      files: [new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf")],
    });
    useSelectionStore.getState().toggle("doc-vinci-1");
    useTopbarStore.getState().setTitle("Groupe Vinci — Lot 03");
    const { wrapper } = sessionWrapper();
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => result.current.logout());

    expect(usePendingFolderUploadStore.getState().pending).toBeNull();
    expect(useSelectionStore.getState().count()).toBe(0);
    expect(useTopbarStore.getState().title).toBeNull();
  });

  it("drops the cached server data on the way out", () => {
    const { wrapper, queryClient } = sessionWrapper();
    queryClient.setQueryData(["projects"], [{ id: "p-1", name: "Lot 03" }]);
    const { result } = renderHook(() => useSession(), { wrapper });

    act(() => result.current.logout());

    expect(queryClient.getQueryData(["projects"])).toBeUndefined();
  });
});

describe("the session identity", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useAuthStore.setState(initialAuth, true);
    localStorage.clear();
  });

  it("stores the identity it fetched when the session did not change", async () => {
    vi.mocked(authService.getMe).mockResolvedValue(ok(tenantAUser));
    authenticate();
    const { wrapper } = sessionWrapper();
    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(useAuthStore.getState().user).toEqual(tenantAUser);
  });

  it("does not hand the previous tenant's identity to the session that replaced it", async () => {
    let release: (result: Awaited<ReturnType<typeof authService.getMe>>) => void =
      () => {};
    const started = new Promise<void>((resolveStarted) => {
      vi.mocked(authService.getMe).mockImplementation(() => {
        resolveStarted();
        return new Promise((resolve) => {
          release = resolve;
        });
      });
    });
    authenticate();
    const { wrapper } = sessionWrapper();
    renderHook(() => useSession(), { wrapper });

    await started;
    await act(async () => {
      useAuthStore.getState().openSession("access-b", "refresh-b");
      release(ok(tenantAUser));
      await Promise.resolve();
    });

    expect(useAuthStore.getState().user).toBeNull();
  });
});

describe("the session contract", () => {
  it("refuses to be read outside its provider", () => {
    const { wrapper } = createQueryClientWrapper();

    expect(() => renderHook(() => useSession(), { wrapper })).toThrow(
      /within a SessionProvider/,
    );
  });
});
