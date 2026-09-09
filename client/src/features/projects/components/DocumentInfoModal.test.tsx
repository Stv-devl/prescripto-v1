/**
 * Representative case for focus-trap adoption across the ten `role="dialog"`
 * modals migrated to `useModalDialog`: focus must move into the dialog on
 * open and return to the trigger element on close. The other nine modals
 * share the same hook and are not re-tested individually for this behaviour.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Document } from "../types/types";
import { DocumentInfoModal } from "./DocumentInfoModal";

const doc: Document = {
  id: "doc-1",
  project_id: "p-1",
  folder_id: null,
  filename: "CCTP-lot-3.pdf",
  type: "cctp",
  lot: "03",
  phase: "execution",
  size: 128_000,
  status: "ready",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function Host({ open }: { open: boolean }): React.ReactElement {
  return (
    <>
      <button type="button">déclencheur</button>
      {open && <DocumentInfoModal document={doc} onClose={vi.fn()} />}
    </>
  );
}

describe("DocumentInfoModal — focus trap", () => {
  it("moves focus into the dialog on open and restores it to the trigger on close", () => {
    const { rerender } = render(<Host open={false} />);
    const trigger = screen.getByRole("button", { name: "déclencheur" });
    trigger.focus();
    expect(trigger).toHaveFocus();

    rerender(<Host open />);

    expect(trigger).not.toHaveFocus();
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    rerender(<Host open={false} />);

    expect(trigger).toHaveFocus();
  });
});
