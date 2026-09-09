import { renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

import * as authService from "@/features/auth/services/auth.service";
import { useLogin, useSignup } from "@/features/auth/hooks/hooks";
import { useAdminStore } from "@/features/admin/stores/store";
import { usePendingFolderUploadStore } from "@/features/projects/stores/pendingFolderUploadStore";
import { useProjectsViewStore } from "@/features/projects/stores/projectsViewStore";
import { useSelectionStore } from "@/features/projects/stores/selectionStore";
import { useUploadStore } from "@/features/projects/stores/uploadStore";
import { ok } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import { useSidebarStore } from "@/lib/store/sidebarStore";
import { useThemeStore } from "@/lib/store/themeStore";
import { useTopbarStore } from "@/lib/store/topbarStore";
import { createQueryClientWrapper } from "@/test/utils";

vi.mock("@/features/auth/services/auth.service");

// Captured at module scope, before any case runs: getState() returns the pristine
// state including the actions, which setState(x, true) would otherwise wipe.
const initialAuth = useAuthStore.getState();
const initialPendingFolderUpload = usePendingFolderUploadStore.getState();
const initialUpload = useUploadStore.getState();
const initialSelection = useSelectionStore.getState();
const initialProjectsView = useProjectsViewStore.getState();
const initialAdmin = useAdminStore.getState();
const initialTopbar = useTopbarStore.getState();
const initialTheme = useThemeStore.getState();
const initialSidebar = useSidebarStore.getState();

interface SixStores {
  pendingFolderName: string | null;
  uploadIds: string[];
  uploadingFolderIds: string[];
  selectedIds: string[];
  adminFilters: Record<string, unknown>;
  adminSelectedChunkId: string | null;
  adminActiveTab: string;
  adminSelectedDocumentId: string | null;
  topbarTitle: string | null;
  searchQuery: string;
  phaseFilter: string | null;
  statusFilter: string | null;
  sortBy: string;
  sortDirection: string;
}

/** The value the six stores hold when nothing of any tenant is left in them. */
const CLEAN: SixStores = {
  pendingFolderName: null,
  uploadIds: [],
  uploadingFolderIds: [],
  selectedIds: [],
  adminFilters: {
    page: 1,
    per_page: 50,
    sort_by: "position",
    sort_order: "asc",
  },
  adminSelectedChunkId: null,
  adminActiveTab: "dashboard",
  adminSelectedDocumentId: null,
  topbarTitle: null,
  searchQuery: "",
  phaseFilter: null,
  statusFilter: "active",
  sortBy: "created_at",
  sortDirection: "desc",
};

function sixStores(): SixStores {
  const projectsView = useProjectsViewStore.getState();
  const admin = useAdminStore.getState();
  return {
    pendingFolderName:
      usePendingFolderUploadStore.getState().pending?.folderName ?? null,
    uploadIds: Object.keys(useUploadStore.getState().uploads),
    uploadingFolderIds: [...useUploadStore.getState().uploadingFolderIds],
    selectedIds: [...useSelectionStore.getState().selectedIds],
    adminFilters: { ...admin.filters },
    adminSelectedChunkId: admin.selectedChunkId,
    adminActiveTab: admin.activeTab,
    adminSelectedDocumentId: admin.selectedDocumentId,
    topbarTitle: useTopbarStore.getState().title,
    searchQuery: projectsView.searchQuery,
    phaseFilter: projectsView.phaseFilter,
    statusFilter: projectsView.statusFilter,
    sortBy: projectsView.sortBy,
    sortDirection: projectsView.sortDirection,
  };
}

function restoreAllStores(): void {
  useAuthStore.setState(initialAuth, true);
  usePendingFolderUploadStore.setState(initialPendingFolderUpload, true);
  useUploadStore.setState(initialUpload, true);
  useSelectionStore.setState(initialSelection, true);
  useProjectsViewStore.setState(initialProjectsView, true);
  useAdminStore.setState(initialAdmin, true);
  useTopbarStore.setState(initialTopbar, true);
  useThemeStore.setState(initialTheme, true);
  useSidebarStore.setState(initialSidebar, true);
}

function seedTenantState(): void {
  usePendingFolderUploadStore.getState().setPending({
    folderName: "Groupe Vinci — Lot 03",
    files: [
      new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf", {
        type: "application/pdf",
      }),
    ],
  });

  useUploadStore.getState().addUpload("up-1", "cctp-lot-03.pdf", "folder-77");
  useUploadStore.getState().addUpload("up-2", "dpgf-lot-03.xlsx", "folder-77");
  useUploadStore.getState().addUploadingFolder("folder-77");

  useSelectionStore.getState().toggle("doc-vinci-1");
  useSelectionStore.getState().toggle("doc-vinci-2");

  useAdminStore.getState().setFilter("search", "Groupe Vinci");
  useAdminStore.getState().selectChunk("chunk-vinci-9");
  useAdminStore.getState().setActiveTab("table");
  useAdminStore.getState().setSelectedDocument("doc-vinci-1");

  useTopbarStore.getState().setTitle("Groupe Vinci — Lot 03");

  useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");
  useProjectsViewStore.getState().setPhaseFilter("dce");
  useProjectsViewStore.getState().setSortBy("name");
}

function storageKeys(): string[] {
  const keys: string[] = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (key) keys.push(key);
  }
  return keys.sort();
}

function storageDump(): string {
  return storageKeys()
    .map((key) => `${key}=${localStorage.getItem(key) ?? ""}`)
    .join("\n");
}

describe("session boundary — logout", () => {
  beforeEach(() => {
    restoreAllStores();
    localStorage.clear();
  });

  it("leaves nothing of the previous tenant in the six feature stores after a logout", () => {
    seedTenantState();

    useAuthStore.getState().logout();

    expect(sixStores()).toEqual(CLEAN);
  });

  it("makes files dropped by the previous tenant unconsumable after a logout", () => {
    usePendingFolderUploadStore.getState().setPending({
      folderName: "Groupe Vinci — Lot 03",
      files: [
        new File(["CCTP gros oeuvre"], "cctp-lot-03.pdf", {
          type: "application/pdf",
        }),
      ],
    });

    useAuthStore.getState().logout();

    expect(usePendingFolderUploadStore.getState().consume()).toBeNull();
  });

  it("keeps the three device preferences across a logout", () => {
    useThemeStore.getState().toggleTheme();
    useSidebarStore.getState().setCollapsed(true);
    useProjectsViewStore.getState().setViewMode("list");
    const chosenTheme = useThemeStore.getState().theme;
    seedTenantState();

    useAuthStore.getState().logout();

    expect(useThemeStore.getState().theme).toBe(chosenTheme);
    expect(useSidebarStore.getState().isCollapsed).toBe(true);
    expect(useProjectsViewStore.getState().viewMode).toBe("list");
  });

  it("leaves the six stores just as clean after a second logout", () => {
    seedTenantState();

    useAuthStore.getState().logout();
    useAuthStore.getState().logout();

    expect(sixStores()).toEqual(CLEAN);
  });

  it("is a non-event on an already clean state", () => {
    useAuthStore.getState().logout();

    expect(sixStores()).toEqual(CLEAN);
  });

  it("never lets the six stores put tenant data in storage", () => {
    seedTenantState();
    useProjectsViewStore.getState().setViewMode("list");

    const dump = storageDump();

    expect(storageKeys()).toEqual(["prescripto-projects-view"]);
    expect(dump).toContain('"viewMode":"list"');
    expect(dump).not.toContain("Groupe Vinci");
    expect(dump).not.toContain("doc-vinci-1");
    expect(dump).not.toContain("cctp-lot-03.pdf");
    expect(dump).not.toContain("chunk-vinci-9");
    expect(dump).not.toContain("folder-77");
  });
});

describe("session boundary — opening a session", () => {
  beforeEach(() => {
    restoreAllStores();
    localStorage.clear();
  });

  it("carries nothing of the previous tenant into the next one, across the whole scenario", () => {
    seedTenantState();
    useAuthStore.getState().logout();

    useAuthStore.getState().openSession("access-b", "refresh-b");

    expect(sixStores()).toEqual(CLEAN);
    expect(useAuthStore.getState().accessToken).toBe("access-b");
  });

  it("starts clean even when the previous session never logged out", () => {
    seedTenantState();

    useAuthStore.getState().openSession("access-b", "refresh-b");

    expect(sixStores()).toEqual(CLEAN);
  });

  it("keeps the three device preferences across a session opening", () => {
    useThemeStore.getState().toggleTheme();
    useSidebarStore.getState().setCollapsed(true);
    useProjectsViewStore.getState().setViewMode("list");
    const chosenTheme = useThemeStore.getState().theme;
    seedTenantState();

    useAuthStore.getState().openSession("access-b", "refresh-b");

    expect(useThemeStore.getState().theme).toBe(chosenTheme);
    expect(useSidebarStore.getState().isCollapsed).toBe(true);
    expect(useProjectsViewStore.getState().viewMode).toBe("list");
  });
});

describe("session boundary — the sign-in hooks that open it", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    restoreAllStores();
    localStorage.clear();
  });

  it("starts a logged-in session on a clean client state", async () => {
    vi.mocked(authService.login).mockResolvedValue(
      ok({ access_token: "acc", refresh_token: "ref", token_type: "bearer" }),
    );
    seedTenantState();
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useLogin(), { wrapper });

    await result.current.mutateAsync({ email: "a@b.fr", password: "secret" });

    expect(sixStores()).toEqual(CLEAN);
  });

  it("drops the previous tenant's cached server data when logging in", async () => {
    vi.mocked(authService.login).mockResolvedValue(
      ok({ access_token: "acc", refresh_token: "ref", token_type: "bearer" }),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    queryClient.setQueryData(["projects"], [{ id: "p-a", name: "Lot 03" }]);
    const { result } = renderHook(() => useLogin(), { wrapper });

    await result.current.mutateAsync({ email: "a@b.fr", password: "secret" });

    expect(queryClient.getQueryData(["projects"])).toBeUndefined();
  });

  it("drops the previous tenant's cached server data when signing up", async () => {
    vi.mocked(authService.signup).mockResolvedValue(
      ok({ access_token: "acc", refresh_token: "ref", token_type: "bearer" }),
    );
    const { wrapper, queryClient } = createQueryClientWrapper();
    queryClient.setQueryData(["projects"], [{ id: "p-a", name: "Lot 03" }]);
    const { result } = renderHook(() => useSignup(), { wrapper });

    await result.current.mutateAsync({
      name: "Camille Roux",
      email: "a@b.fr",
      password: "secret",
    });

    expect(queryClient.getQueryData(["projects"])).toBeUndefined();
  });

  it("starts a signed-up session on a clean client state", async () => {
    vi.mocked(authService.signup).mockResolvedValue(
      ok({ access_token: "acc", refresh_token: "ref", token_type: "bearer" }),
    );
    seedTenantState();
    const { wrapper } = createQueryClientWrapper();
    const { result } = renderHook(() => useSignup(), { wrapper });

    await result.current.mutateAsync({
      name: "Camille Roux",
      email: "a@b.fr",
      password: "secret",
    });

    expect(sixStores()).toEqual(CLEAN);
  });
});

describe("session boundary — renewing tokens", () => {
  beforeEach(() => {
    restoreAllStores();
    localStorage.clear();
  });

  it("keeps the work in progress when tokens are renewed mid-session", () => {
    useAuthStore.getState().openSession("access-1", "refresh-1");
    seedTenantState();

    useAuthStore.getState().renewTokens("access-2", "refresh-2");

    expect(usePendingFolderUploadStore.getState().pending?.folderName).toBe(
      "Groupe Vinci — Lot 03",
    );
    expect(useSelectionStore.getState().count()).toBe(2);
    expect(Object.keys(useUploadStore.getState().uploads)).toEqual([
      "up-1",
      "up-2",
    ]);
    expect(useAuthStore.getState().accessToken).toBe("access-2");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-2");
  });
});
