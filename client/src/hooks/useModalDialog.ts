import { useEffect, useId, useRef, type RefObject } from "react";
import { focusableWithin } from "@/lib/focusable";
import { acquire, release } from "@/lib/refCount";

/**
 * Read-only so it stays covariant: a `RefObject<HTMLDivElement | null>` is a
 * valid fallback, and `RefObject` itself is invariant because it is writable.
 * Nothing here ever assigns to `.current`.
 */
export type ReadOnlyRef = { readonly current: HTMLElement | null };

interface UseModalDialogOptions {
  isOpen: boolean;
  /** Focused when the trigger is gone by the time the dialog closes. */
  fallbackFocusRef?: ReadOnlyRef;
  /**
   * Focused on open instead of the first focusable descendant — a
   * destructive dialog's Cancel button, a create form's named field, a
   * success dialog's primary action. Ignored when absent or when the target
   * is no longer reachable (removed, disabled, hidden); the default applies.
   */
  initialFocusRef?: ReadOnlyRef;
}

interface UseModalDialogResult<T extends HTMLElement> {
  dialogRef: RefObject<T | null>;
  titleId: string;
}

/**
 * The application root — the one node made inert while a dialog is open.
 *
 * Not the dialog's siblings: the backdrop is one, and making it inert would
 * kill the click-outside close. The dialog lives in a portal on `<body>`, so
 * this single element covers sidebar, topbar and page alike.
 *
 * Returns null under vitest, where the harness renders into a plain container.
 * Callers no-op rather than throw, or every existing consumer suite breaks.
 */
function getAppRoot(): HTMLElement | null {
  return document.getElementById("root");
}

/**
 * Hands focus back once the background is interactive again.
 *
 * `<body>` is never a real trigger: clicking a non-focusable row leaves it as
 * `activeElement`, `document.contains` says it survived, and focusing it is a
 * no-op — silently skipping the fallback on the most common path. The call
 * order also matters, invisibly: while the root is still inert, `focus()` does
 * nothing at all, and jsdom implements no part of `inert`.
 */
function restoreFocus(
  trigger: HTMLElement | null,
  fallback: HTMLElement | null | undefined,
): void {
  const usable =
    trigger && trigger !== document.body && document.contains(trigger)
      ? trigger
      : fallback;
  if (usable && document.contains(usable)) usable.focus();
}

/**
 * Turns a container into a modal dialog: traps focus, makes the rest of the
 * app inert, locks background scroll, and restores focus on close. `inert`
 * and the scroll lock are reference counted, so a dialog opened over another
 * never lifts either too early. `inert` only applies when the dialog is
 * portalled OUTSIDE `#root` — seven of the ten modals in this app are not,
 * so it is skipped there. Escape is deliberately not handled here.
 */
export function useModalDialog<T extends HTMLElement = HTMLElement>({
  isOpen,
  fallbackFocusRef,
  initialFocusRef,
}: UseModalDialogOptions): UseModalDialogResult<T> {
  const dialogRef = useRef<T | null>(null);
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) return;
    const dialog = dialogRef.current;
    if (!dialog) return;

    const trigger = document.activeElement as HTMLElement | null;
    const fallback = fallbackFocusRef?.current;
    const appRoot = getAppRoot();
    const background = appRoot && !appRoot.contains(dialog) ? appRoot : null;
    if (background) {
      acquire(background, () => background.setAttribute("inert", ""));
    }

    const body = document.body;
    acquire(body, () => body.classList.add("overflow-hidden"));

    const preferred = initialFocusRef?.current;
    const initiallyFocusable = focusableWithin(dialog);
    const initial =
      preferred && initiallyFocusable.includes(preferred)
        ? preferred
        : (initiallyFocusable[0] ?? dialog);
    initial.focus();

    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== "Tab") return;

      const focusable = focusableWithin(dialog);
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      release(body, () => body.classList.remove("overflow-hidden"));
      if (background) {
        release(background, () => background.removeAttribute("inert"));
      }
      restoreFocus(trigger, fallback);
    };
  }, [isOpen, fallbackFocusRef, initialFocusRef]);

  return { dialogRef, titleId };
}
