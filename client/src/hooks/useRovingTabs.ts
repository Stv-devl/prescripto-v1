import { useRef, type KeyboardEvent } from "react";

interface UseRovingTabsResult<T extends string> {
  /** Ref callback to attach to each item's button, keyed by its own value. */
  setRef: (item: T) => (el: HTMLButtonElement | null) => void;
  /** Keydown handler to attach to each item's button. */
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>, item: T) => void;
  /** `0` for the active item, `-1` for every other — the roving part. */
  tabIndexFor: (item: T) => 0 | -1;
}

/**
 * Roving tabindex for a horizontal list of buttons (a tablist): arrow keys
 * move AND activate, `Home`/`End` jump to the extremities, and only the
 * active item stays in the browser's Tab order.
 */
export function useRovingTabs<T extends string>(
  items: readonly T[],
  active: T,
  onActivate: (item: T) => void,
): UseRovingTabsResult<T> {
  const refs = useRef(new Map<T, HTMLButtonElement | null>());

  function move(next: T): void {
    onActivate(next);
    refs.current.get(next)?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, item: T): void {
    const index = items.indexOf(item);
    if (index === -1) return;

    switch (event.key) {
      case "ArrowRight":
        event.preventDefault();
        move(items[(index + 1) % items.length]);
        return;
      case "ArrowLeft":
        event.preventDefault();
        move(items[(index - 1 + items.length) % items.length]);
        return;
      case "Home":
        event.preventDefault();
        move(items[0]);
        return;
      case "End":
        event.preventDefault();
        move(items[items.length - 1]);
        return;
      default:
        return;
    }
  }

  return {
    setRef: (item: T) => (el: HTMLButtonElement | null) => {
      refs.current.set(item, el);
    },
    onKeyDown,
    tabIndexFor: (item: T) => (item === active ? 0 : -1),
  };
}
