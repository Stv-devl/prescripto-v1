/**
 * Representative case for `initialFocusRef` across the six modals that use
 * it to redirect the initial focus away from the first focusable element:
 * a destructive modal must land focus on Cancel, never on Delete, since a
 * silent wrong target here is the worst case (an accidental confirm on the
 * next keystroke). The other five modals share the same hook argument and
 * are not re-tested individually for this behaviour.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DeleteFolderModal } from "./DeleteFolderModal";

describe("DeleteFolderModal — initial focus", () => {
  it("focuses Cancel on open, not the destructive Delete action", () => {
    render(
      <DeleteFolderModal
        folderName="Lot 03"
        isPending={false}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Annuler" })).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Supprimer" }),
    ).not.toHaveFocus();
  });
});
