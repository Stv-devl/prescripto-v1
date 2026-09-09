import { beforeEach, describe, expect, it } from "vitest";

import { useTopbarStore } from "./topbarStore";

const initialTopbar = useTopbarStore.getState();

describe("topbar store", () => {
  beforeEach(() => {
    useTopbarStore.setState(initialTopbar, true);
  });

  it("shows the title it is given", () => {
    useTopbarStore.getState().setTitle("Groupe Vinci — Lot 03");

    expect(useTopbarStore.getState().title).toBe("Groupe Vinci — Lot 03");
  });

  it("shows no title after a reset, so a project name does not outlive its session", () => {
    useTopbarStore.getState().setTitle("Groupe Vinci — Lot 03");

    useTopbarStore.getState().reset();

    expect(useTopbarStore.getState().title).toBeNull();
  });
});
