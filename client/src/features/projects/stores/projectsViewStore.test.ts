import { beforeEach, describe, expect, it } from "vitest";

import { useProjectsViewStore } from "./projectsViewStore";

const VIEW_STORAGE_KEY = "prescripto-projects-view";

const initialProjectsView = useProjectsViewStore.getState();

describe("projects view store", () => {
  beforeEach(() => {
    useProjectsViewStore.setState(initialProjectsView, true);
    localStorage.clear();
  });

  it("returns every filter to its starting value on reset", () => {
    useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");
    useProjectsViewStore.getState().setPhaseFilter("dce");
    useProjectsViewStore.getState().setStatusFilter("archived");
    useProjectsViewStore.getState().setSortBy("name");
    useProjectsViewStore.getState().setSortDirection("asc");

    useProjectsViewStore.getState().resetFilters();

    expect(useProjectsViewStore.getState().searchQuery).toBe("");
    expect(useProjectsViewStore.getState().phaseFilter).toBeNull();
    expect(useProjectsViewStore.getState().statusFilter).toBe("active");
    expect(useProjectsViewStore.getState().sortBy).toBe("created_at");
    expect(useProjectsViewStore.getState().sortDirection).toBe("desc");
  });

  it("keeps the view mode across a reset, because it is a device preference", () => {
    useProjectsViewStore.getState().setViewMode("list");
    useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");

    useProjectsViewStore.getState().resetFilters();

    expect(useProjectsViewStore.getState().viewMode).toBe("list");
  });

  it("clears the phase filter when the same phase is chosen twice", () => {
    useProjectsViewStore.getState().setPhaseFilter("dce");
    expect(useProjectsViewStore.getState().phaseFilter).toBe("dce");

    useProjectsViewStore.getState().setPhaseFilter("dce");
    expect(useProjectsViewStore.getState().phaseFilter).toBeNull();
  });

  it("clears the status filter when the same status is chosen twice", () => {
    useProjectsViewStore.getState().setStatusFilter("archived");
    expect(useProjectsViewStore.getState().statusFilter).toBe("archived");

    useProjectsViewStore.getState().setStatusFilter("archived");
    expect(useProjectsViewStore.getState().statusFilter).toBeNull();
  });

  it("takes the search text, the sort column and the sort direction as given", () => {
    useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");
    useProjectsViewStore.getState().setSortBy("document_count");
    useProjectsViewStore.getState().setSortDirection("asc");

    expect(useProjectsViewStore.getState().searchQuery).toBe("Groupe Vinci");
    expect(useProjectsViewStore.getState().sortBy).toBe("document_count");
    expect(useProjectsViewStore.getState().sortDirection).toBe("asc");
  });

  it("changes the view mode without disturbing the filters", () => {
    useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");

    useProjectsViewStore.getState().setViewMode("list");

    expect(useProjectsViewStore.getState().searchQuery).toBe("Groupe Vinci");
    expect(useProjectsViewStore.getState().viewMode).toBe("list");
  });

  it("writes only the view mode to storage, so no filter text outlives the session", () => {
    useProjectsViewStore.getState().setViewMode("list");
    useProjectsViewStore.getState().setSearchQuery("Groupe Vinci");

    const raw = localStorage.getItem(VIEW_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw ?? "")).toEqual({
      state: { viewMode: "list" },
      version: 0,
    });
  });
});
