import { beforeEach, describe, expect, it } from "vitest";

import { useSelectionStore } from "./selectionStore";

const initialSelection = useSelectionStore.getState();

describe("selection store", () => {
  beforeEach(() => {
    useSelectionStore.setState(initialSelection, true);
  });

  it("selects nothing after being cleared", () => {
    useSelectionStore.getState().toggle("doc-1");
    useSelectionStore.getState().toggle("doc-2");

    useSelectionStore.getState().clear();

    expect(useSelectionStore.getState().count()).toBe(0);
  });

  it("hands out a fresh selection set on clear, so two sessions never share one", () => {
    useSelectionStore.getState().clear();
    const firstSession = useSelectionStore.getState().selectedIds;
    firstSession.add("doc-vinci-1");

    useSelectionStore.getState().clear();

    expect(useSelectionStore.getState().count()).toBe(0);
  });

  it("adds a document that was not selected and removes one that was", () => {
    useSelectionStore.getState().toggle("doc-1");
    expect(useSelectionStore.getState().isSelected("doc-1")).toBe(true);

    useSelectionStore.getState().toggle("doc-1");
    expect(useSelectionStore.getState().isSelected("doc-1")).toBe(false);
  });

  it("selects the whole list when none is selected, and empties it when all are", () => {
    useSelectionStore.getState().toggleAll(["doc-1", "doc-2"]);
    expect(useSelectionStore.getState().count()).toBe(2);

    useSelectionStore.getState().toggleAll(["doc-1", "doc-2"]);
    expect(useSelectionStore.getState().count()).toBe(0);
  });

  it("tells a selected document apart from one that is not", () => {
    useSelectionStore.getState().toggle("doc-1");

    expect(useSelectionStore.getState().isSelected("doc-1")).toBe(true);
    expect(useSelectionStore.getState().isSelected("doc-2")).toBe(false);
  });

  it("tells nothing, some and all selected apart", () => {
    const all = ["doc-1", "doc-2"];

    expect(useSelectionStore.getState().isAllSelected(all)).toBe(false);
    expect(useSelectionStore.getState().isPartiallySelected(all)).toBe(false);

    useSelectionStore.getState().toggle("doc-1");
    expect(useSelectionStore.getState().isAllSelected(all)).toBe(false);
    expect(useSelectionStore.getState().isPartiallySelected(all)).toBe(true);

    useSelectionStore.getState().toggle("doc-2");
    expect(useSelectionStore.getState().isAllSelected(all)).toBe(true);
    expect(useSelectionStore.getState().isPartiallySelected(all)).toBe(false);
  });

  it("counts the selected documents", () => {
    useSelectionStore.getState().toggle("doc-1");
    useSelectionStore.getState().toggle("doc-2");

    expect(useSelectionStore.getState().count()).toBe(2);
  });

  it("does not claim an empty list is fully selected", () => {
    expect(useSelectionStore.getState().isAllSelected([])).toBe(false);
  });
});
