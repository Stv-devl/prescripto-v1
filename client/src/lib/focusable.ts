/**
 * Everything the browser will actually stop on when tabbing.
 *
 * `summary`, `iframe`, media with controls and `contenteditable` are easy to
 * forget, and each omission breaks a focus trap silently: missed at the end of
 * the list, the real last element is skipped and Tab escapes the dialog.
 */
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button",
  "input",
  "select",
  "textarea",
  "summary",
  "iframe",
  "audio[controls]",
  "video[controls]",
  "[contenteditable]",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

/**
 * Weeds out what matches the selector but cannot take focus.
 *
 * A `<fieldset disabled>` disables its descendants without giving any of them
 * a `disabled` attribute, and `input[type=hidden]` matches `input`. Each puts
 * a dead element at the head or tail of the list and breaks the trap. No
 * geometry test: jsdom performs no layout, so it would exclude everything.
 */
function isReachable(el: HTMLElement): boolean {
  if (el.hasAttribute("disabled")) return false;
  if (el.hasAttribute("hidden")) return false;
  if (el instanceof HTMLInputElement && el.type === "hidden") return false;
  return el.closest("fieldset[disabled]") === null;
}

/**
 * Focusable descendants, in document order.
 *
 * Never cache the result: a dialog's contents change while it is open — an
 * editing textarea appears, buttons load in — so a list captured at open time
 * goes stale on screen.
 */
export function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter(isReachable);
}
