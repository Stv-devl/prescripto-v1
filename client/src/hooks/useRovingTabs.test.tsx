import { useState, type ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRovingTabs } from "./useRovingTabs";

const ITEMS = ["a", "b", "c"] as const;
type Item = (typeof ITEMS)[number];

interface RovingListProps {
  onActivate: (item: Item) => void;
  initial?: Item;
}

function RovingList({ onActivate, initial = "a" }: RovingListProps): ReactElement {
  const [active, setActive] = useState<Item>(initial);
  const { setRef, onKeyDown, tabIndexFor } = useRovingTabs<Item>(ITEMS, active, (item) => {
    setActive(item);
    onActivate(item);
  });
  return (
    <div>
      {ITEMS.map((item) => (
        <button
          key={item}
          ref={setRef(item)}
          tabIndex={tabIndexFor(item)}
          onKeyDown={(event) => onKeyDown(event, item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}

describe("useRovingTabs — comportement principal", () => {
  it("ArrowRight déplace vers l'élément suivant, active et pose le focus", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} />);
    screen.getByText("a").focus();

    await user.keyboard("{ArrowRight}");

    expect(onActivate).toHaveBeenCalledWith("b");
    expect(screen.getByText("b")).toHaveFocus();
  });

  it("ArrowLeft déplace vers l'élément précédent, active et pose le focus", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} initial="b" />);
    screen.getByText("b").focus();

    await user.keyboard("{ArrowLeft}");

    expect(onActivate).toHaveBeenCalledWith("a");
    expect(screen.getByText("a")).toHaveFocus();
  });
});

describe("useRovingTabs — règles métier", () => {
  it("ArrowRight sur le dernier élément boucle vers le premier", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} initial="c" />);
    screen.getByText("c").focus();

    await user.keyboard("{ArrowRight}");

    expect(onActivate).toHaveBeenCalledWith("a");
  });

  it("ArrowLeft sur le premier élément boucle vers le dernier", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} initial="a" />);
    screen.getByText("a").focus();

    await user.keyboard("{ArrowLeft}");

    expect(onActivate).toHaveBeenCalledWith("c");
  });

  it("Home active le premier élément et y pose le focus, quelle que soit la position de départ", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} initial="c" />);
    screen.getByText("c").focus();

    await user.keyboard("{Home}");

    expect(onActivate).toHaveBeenCalledWith("a");
    expect(screen.getByText("a")).toHaveFocus();
  });

  it("End active le dernier élément et y pose le focus, quelle que soit la position de départ", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} initial="a" />);
    screen.getByText("a").focus();

    await user.keyboard("{End}");

    expect(onActivate).toHaveBeenCalledWith("c");
    expect(screen.getByText("c")).toHaveFocus();
  });

  it("tabIndexFor rend 0 pour l'élément actif et -1 pour tous les autres", () => {
    render(<RovingList onActivate={vi.fn()} initial="b" />);

    expect(screen.getByText("a")).toHaveAttribute("tabindex", "-1");
    expect(screen.getByText("b")).toHaveAttribute("tabindex", "0");
    expect(screen.getByText("c")).toHaveAttribute("tabindex", "-1");
  });
});

describe("useRovingTabs — cas limites", () => {
  it("une touche non gérée n'appelle pas onActivate", async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    render(<RovingList onActivate={onActivate} />);
    screen.getByText("a").focus();

    await user.keyboard("x");

    expect(onActivate).not.toHaveBeenCalled();
  });
});
