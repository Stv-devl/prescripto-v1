/**
 * What jsdom can and cannot witness here matters, so it is said once:
 *
 * jsdom 27 implements no part of `inert` — neither the attribute's effect nor
 * the property. These cases therefore assert that the attribute is PUT on and
 * taken off #root, never that the background actually stopped being reachable.
 * That last one needs a real browser and is deliberately left to the E2E
 * harness.
 */
import { useRef, type ReactElement, type ReactNode, type RefObject } from "react";
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useModalDialog } from "./useModalDialog";

interface DialogProps {
  isOpen: boolean;
  children?: ReactNode;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
}

function Dialog({
  isOpen,
  children,
  fallbackFocusRef,
  initialFocusRef,
}: DialogProps): ReactElement | null {
  const { dialogRef, titleId } = useModalDialog({ isOpen, fallbackFocusRef, initialFocusRef });
  if (!isOpen) return null;
  return (
    <section ref={dialogRef} tabIndex={-1} aria-labelledby={titleId} data-testid="dialog">
      {children}
    </section>
  );
}

/**
 * #root plus a dialog rendered OUTSIDE it — the portalled shape the hook
 * requires. Rendering the dialog inside #root is the broken configuration:
 * it would make itself inert, and jsdom would say nothing.
 */
function renderBesideAppRoot(ui: ReactElement) {
  const root = document.createElement("div");
  root.id = "root";
  document.body.appendChild(root);
  const host = document.createElement("div");
  document.body.appendChild(host);
  return { root, host, ...render(ui, { container: host }) };
}

describe("useModalDialog — focus trap", () => {
  it("wraps Shift+Tab from the first element back to the last", async () => {
    const user = userEvent.setup();
    render(
      <Dialog isOpen>
        <button type="button">first</button>
        <button type="button">last</button>
      </Dialog>,
    );
    const first = document.querySelector<HTMLElement>("button")!;
    const last = document.querySelectorAll<HTMLElement>("button")[1];

    first.focus();
    await user.tab({ shift: true });

    expect(last).toHaveFocus();
  });

  it("keeps focus on the only focusable element, in both directions", async () => {
    const user = userEvent.setup();
    render(
      <Dialog isOpen>
        <button type="button">only</button>
      </Dialog>,
    );
    const only = document.querySelector<HTMLElement>("button")!;

    await user.tab();
    expect(only).toHaveFocus();

    await user.tab({ shift: true });
    expect(only).toHaveFocus();
  });

  it("holds focus on the container when nothing inside is focusable", async () => {
    const user = userEvent.setup();
    const { getByTestId } = render(<Dialog isOpen>plain text</Dialog>);
    const dialog = getByTestId("dialog");

    expect(dialog).toHaveFocus();

    await user.tab();

    expect(dialog).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });

  it("recomputes the focusable list instead of freezing it at open time", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <Dialog isOpen>
        <button type="button">first</button>
        <button type="button">last</button>
      </Dialog>,
    );

    rerender(
      <Dialog isOpen>
        <button type="button">first</button>
        <button type="button">added later</button>
      </Dialog>,
    );

    const added = document.querySelectorAll<HTMLElement>("button")[1];
    added.focus();
    await user.tab();

    expect(document.querySelector("button")).toHaveFocus();
  });

  it("drops an element that became disabled from the loop", async () => {
    // The disabled button must be LAST in document order, so that keeping it in
    // the list would make it `last` and swallow the wrap. Putting it in the
    // middle leaves the assertion true either way — which is how this case was
    // first written, and it stayed green with the filter deleted.
    const user = userEvent.setup();
    const { rerender } = render(
      <Dialog isOpen>
        <button type="button">first</button>
        <button type="button">last</button>
      </Dialog>,
    );

    rerender(
      <Dialog isOpen>
        <button type="button">first</button>
        <button type="button">middle</button>
        <button type="button" disabled>
          last
        </button>
      </Dialog>,
    );

    const buttons = document.querySelectorAll<HTMLElement>("button");
    buttons[1].focus();
    await user.tab();

    expect(buttons[0]).toHaveFocus();
  });
});

describe("useModalDialog — initial focus and restoration", () => {
  it("moves focus into the dialog on open", () => {
    render(
      <Dialog isOpen>
        <button type="button">inside</button>
      </Dialog>,
    );

    expect(document.querySelector("button")).toHaveFocus();
  });

  it("returns focus to the trigger when the dialog unmounts", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const { unmount } = render(
      <Dialog isOpen>
        <button type="button">inside</button>
      </Dialog>,
    );
    unmount();

    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("restores focus to a div trigger, not only to a real button", () => {
    const trigger = document.createElement("div");
    trigger.setAttribute("role", "button");
    trigger.tabIndex = 0;
    document.body.appendChild(trigger);
    trigger.focus();

    const { unmount } = render(
      <Dialog isOpen>
        <button type="button">inside</button>
      </Dialog>,
    );
    unmount();

    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("falls back to a stable container when the trigger is gone", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    // The list outlives the dialog, exactly as AdminDashboard outlives the
    // ChunkDetail it renders conditionally. Unmounting both at once would test
    // a path the application never takes.
    function WithFallback({ open }: { open: boolean }): ReactElement {
      const fallback = useRef<HTMLDivElement | null>(null);
      return (
        <>
          <div ref={fallback} tabIndex={-1} data-testid="list" />
          {open && (
            <Dialog isOpen fallbackFocusRef={fallback}>
              <button type="button">inside</button>
            </Dialog>
          )}
        </>
      );
    }

    const { rerender, getByTestId } = render(<WithFallback open />);
    const list = getByTestId("list");
    trigger.remove();

    rerender(<WithFallback open={false} />);

    expect(list).toHaveFocus();
    expect(document.body).not.toHaveFocus();
  });
});

describe("useModalDialog — background inertness", () => {
  it("marks the app root inert while open", () => {
    const { root, host } = renderBesideAppRoot(<Dialog isOpen>text</Dialog>);

    expect(root.hasAttribute("inert")).toBe(true);

    root.remove();
    host.remove();
  });

  it("never makes itself inert when it lives inside the app root", () => {
    // Seven of the ten modals in this app are not portalled yet. Adopting the
    // hook must not kill them: an inert #root containing the dialog would make
    // its own controls unfocusable and drop it from the accessibility tree.
    const root = document.createElement("div");
    root.id = "root";
    document.body.appendChild(root);

    const { unmount } = render(
      <Dialog isOpen>
        <button type="button">inside</button>
      </Dialog>,
      { container: root },
    );

    expect(root.hasAttribute("inert")).toBe(false);
    expect(document.querySelector("button")).toHaveFocus();

    unmount();
    root.remove();
  });

  it("leaves nothing inert once closed", () => {
    const { root, host, unmount } = renderBesideAppRoot(<Dialog isOpen>text</Dialog>);

    unmount();

    expect(root.hasAttribute("inert")).toBe(false);
    expect(document.querySelector("[inert]")).toBeNull();
    root.remove();
    host.remove();
  });

  it("leaves the DOM as it found it after two mount/unmount cycles", () => {
    const before = document.body.innerHTML;

    const firstPass = renderBesideAppRoot(<Dialog isOpen>text</Dialog>);
    firstPass.unmount();
    firstPass.root.remove();
    firstPass.host.remove();

    const secondPass = renderBesideAppRoot(<Dialog isOpen>text</Dialog>);
    secondPass.unmount();
    secondPass.root.remove();
    secondPass.host.remove();

    expect(document.body.innerHTML).toBe(before);
    expect(document.querySelector("[inert]")).toBeNull();
  });

  it("does not throw when no app root exists, as in every consumer suite", () => {
    expect(() => {
      const { unmount } = render(<Dialog isOpen>text</Dialog>);
      unmount();
    }).not.toThrow();
  });

  it("stays inert while a second, later-opened dialog is still open", () => {
    function Stack({ second }: { second: boolean }): ReactElement {
      return (
        <>
          <Dialog isOpen>first</Dialog>
          {second && <Dialog isOpen>second</Dialog>}
        </>
      );
    }

    const root = document.createElement("div");
    root.id = "root";
    document.body.appendChild(root);
    const host = document.createElement("div");
    document.body.appendChild(host);

    const { rerender, unmount } = render(<Stack second />, { container: host });
    expect(root.hasAttribute("inert")).toBe(true);

    // The second dialog closes first — the shared root must stay inert.
    rerender(<Stack second={false} />);
    expect(root.hasAttribute("inert")).toBe(true);

    unmount();
    expect(root.hasAttribute("inert")).toBe(false);
    root.remove();
    host.remove();
  });
});

describe("useModalDialog — background scroll lock", () => {
  it("locks body scroll while open and releases it on close", () => {
    const { unmount } = render(<Dialog isOpen>text</Dialog>);

    expect(document.body.classList.contains("overflow-hidden")).toBe(true);

    unmount();

    expect(document.body.classList.contains("overflow-hidden")).toBe(false);
  });

  it("keeps the lock while a second, later-opened dialog is still open", () => {
    function Stack({ second }: { second: boolean }): ReactElement {
      return (
        <>
          <Dialog isOpen>first</Dialog>
          {second && <Dialog isOpen>second</Dialog>}
        </>
      );
    }

    const { rerender, unmount } = render(<Stack second />);
    expect(document.body.classList.contains("overflow-hidden")).toBe(true);

    rerender(<Stack second={false} />);
    expect(document.body.classList.contains("overflow-hidden")).toBe(true);

    unmount();
    expect(document.body.classList.contains("overflow-hidden")).toBe(false);
  });
});

describe("useModalDialog — initial focus target", () => {
  it("focuses the preferred target instead of the first focusable element", () => {
    function WithPreferred(): ReactElement {
      const secondRef = useRef<HTMLButtonElement>(null);
      return (
        <Dialog isOpen initialFocusRef={secondRef}>
          <button type="button">first</button>
          <button ref={secondRef} type="button">
            second
          </button>
        </Dialog>
      );
    }

    const { getByText } = render(<WithPreferred />);

    expect(getByText("second")).toHaveFocus();
  });

  it("falls back to the first focusable element when the preferred target is outside the dialog", () => {
    const outside = document.createElement("button");
    outside.textContent = "outside";
    document.body.appendChild(outside);

    const { getByText } = render(
      <Dialog isOpen initialFocusRef={{ current: outside }}>
        <button type="button">inside</button>
      </Dialog>,
    );

    expect(getByText("inside")).toHaveFocus();
    outside.remove();
  });

  it("falls back to the first focusable element when the preferred target is disabled", () => {
    function WithDisabledPreferred(): ReactElement {
      const preferredRef = useRef<HTMLButtonElement>(null);
      return (
        <Dialog isOpen initialFocusRef={preferredRef}>
          <button type="button">first</button>
          <button ref={preferredRef} type="button" disabled>
            disabled preferred
          </button>
        </Dialog>
      );
    }

    const { getByText } = render(<WithDisabledPreferred />);

    expect(getByText("first")).toHaveFocus();
  });
});
