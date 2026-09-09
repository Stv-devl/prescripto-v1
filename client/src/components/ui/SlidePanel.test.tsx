/**
 * SlidePanel behaves like a modal — a fixed backdrop covering the app — so it
 * must be one for the keyboard too.
 *
 * The first case reproduces what pass 6 of the admin-error-states review found:
 * with the panel open, Tab reaches a control sitting behind the backdrop,
 * invisible but live. It is reduced here to its minimal shape — one button
 * rendered outside the panel — because the defect has nothing to do with chunk
 * cards, and everything to do with the panel not trapping focus.
 */
import { useRef } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SlidePanel } from "./SlidePanel";

function OpenPanelWithOutsideButton(): React.ReactElement {
  return (
    <>
      <button type="button">outside</button>
      <SlidePanel isOpen onClose={vi.fn()} title="Détail">
        <button type="button">inside</button>
      </SlidePanel>
    </>
  );
}

describe("SlidePanel — focus containment", () => {
  it("keeps Tab inside the panel instead of reaching a control behind the backdrop", async () => {
    const user = userEvent.setup();
    render(<OpenPanelWithOutsideButton />);

    const inside = screen.getByRole("button", { name: "inside" });
    const outside = screen.getByRole("button", { name: "outside" });
    const close = screen.getByRole("button", { name: "Fermer" });

    inside.focus();
    expect(inside).toHaveFocus();

    // Tabbing from the last focusable element of the panel must wrap back into
    // it. Two presses, because leaving the panel first lands on <body> — which
    // is already the defect — and only then reaches the outside control.
    await user.tab();
    await user.tab();

    expect(outside).not.toHaveFocus();
    expect([inside, close]).toContain(document.activeElement);
  });
});

describe("SlidePanel — dialog semantics", () => {
  it("announces itself as a modal dialog labelled by its own title", () => {
    render(
      <SlidePanel isOpen onClose={vi.fn()} title="Détail du chunk">
        contenu
      </SlidePanel>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");

    // The label must resolve to the heading, not merely point somewhere.
    const labelledBy = dialog.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy!)).toHaveTextContent(
      "Détail du chunk",
    );
  });

  it("renders outside the tree it was mounted into", () => {
    const { container } = render(
      <SlidePanel isOpen onClose={vi.fn()} title="Détail">
        contenu
      </SlidePanel>,
    );

    const dialog = screen.getByRole("dialog");
    expect(container).not.toContainElement(dialog);
  });
});

describe("SlidePanel — focus returns to the opener", () => {
  /**
   * The composition the hook suite cannot reach: a real trigger, the real
   * SlidePanel inside its portal and AnimatePresence, and the real close path
   * — the parent unmounting it. Criterion 3 is about this chain, not about the
   * hook in isolation.
   */
  function Host({ open }: { open: boolean }): React.ReactElement {
    return (
      <>
        <button type="button">déclencheur</button>
        {open && (
          <SlidePanel isOpen onClose={vi.fn()} title="Détail">
            <button type="button">inside</button>
          </SlidePanel>
        )}
      </>
    );
  }

  it("hands focus back to the element that opened it", () => {
    const { rerender } = render(<Host open={false} />);
    const trigger = screen.getByRole("button", { name: "déclencheur" });
    trigger.focus();

    rerender(<Host open />);
    expect(trigger).not.toHaveFocus();

    rerender(<Host open={false} />);

    expect(trigger).toHaveFocus();
  });

  it("uses the fallback when the opener is a non-focusable row", () => {
    // ChunkTable opens the panel from a bare <tr onClick>: nothing takes focus,
    // so activeElement is <body>. Counting that as a surviving trigger would
    // skip the fallback and drop focus at the top of the document.
    function RowHost({ open }: { open: boolean }): React.ReactElement {
      const fallback = useRef<HTMLDivElement | null>(null);
      return (
        <>
          <div ref={fallback} tabIndex={-1} data-testid="list" />
          {open && (
            <SlidePanel isOpen onClose={vi.fn()} title="Détail" fallbackFocusRef={fallback}>
              <button type="button">inside</button>
            </SlidePanel>
          )}
        </>
      );
    }

    const { rerender, getByTestId } = render(<RowHost open={false} />);
    document.body.focus();

    rerender(<RowHost open />);
    rerender(<RowHost open={false} />);

    expect(getByTestId("list")).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });
});

describe("SlidePanel — the three ways out", () => {
  it("closes on the Fermer button", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <SlidePanel isOpen onClose={onClose} title="Détail">
        contenu
      </SlidePanel>,
    );

    await user.click(screen.getByRole("button", { name: "Fermer" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on a backdrop click — the backdrop is never made inert", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { baseElement } = render(
      <SlidePanel isOpen onClose={onClose} title="Détail">
        contenu
      </SlidePanel>,
    );

    const backdrop = baseElement.querySelector('[aria-hidden="true"]');
    await user.click(backdrop!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <SlidePanel isOpen onClose={onClose} title="Détail">
        contenu
      </SlidePanel>,
    );

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
