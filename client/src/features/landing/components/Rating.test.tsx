import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Rating } from "./Rating";

function marks(container: HTMLElement): { filled: number; empty: number } {
  return {
    filled: container.querySelectorAll('[data-filled="true"]').length,
    empty: container.querySelectorAll('[data-filled="false"]').length,
  };
}

describe("Rating — five marks, filled up to the value", () => {
  it("fills four marks and leaves one empty for a rating of four", () => {
    const { container } = render(<Rating value={4} />);

    expect(marks(container)).toEqual({ filled: 4, empty: 1 });
  });

  it("fills every mark for a rating of five", () => {
    const { container } = render(<Rating value={5} />);

    expect(marks(container)).toEqual({ filled: 5, empty: 0 });
  });

  it("announces the rating to assistive technology", () => {
    render(<Rating value={4} />);

    expect(screen.getByRole("img", { name: "Note : 4 sur 5" })).toBeVisible();
  });

  it("fills a mark visibly, and leaves the others visibly unfilled", () => {
    const { container } = render(<Rating value={3} />);

    expect(
      container.querySelector('[data-filled="true"]')?.className,
    ).toContain("bg-[#FFC300]");
    expect(
      container.querySelector('[data-filled="false"]')?.className,
    ).not.toContain("bg-[#FFC300]");
  });

  it("rounds a fractional rating, in the marks and in the label alike", () => {
    const { container } = render(<Rating value={4.6} />);

    expect(marks(container)).toEqual({ filled: 5, empty: 0 });
    expect(screen.getByRole("img", { name: "Note : 5 sur 5" })).toBeVisible();
  });

  it("always renders five marks, whatever the rating", () => {
    const { container } = render(<Rating value={2} />);
    const { filled, empty } = marks(container);

    expect(filled + empty).toBe(5);
  });

  it("leaves every mark empty for a rating of zero, and says so", () => {
    const { container } = render(<Rating value={0} />);

    expect(marks(container)).toEqual({ filled: 0, empty: 5 });
    expect(screen.getByRole("img", { name: "Note : 0 sur 5" })).toBeVisible();
  });

  it("caps a rating above five, in the marks and in the label alike", () => {
    const { container } = render(<Rating value={7} />);

    expect(marks(container)).toEqual({ filled: 5, empty: 0 });
    expect(screen.getByRole("img", { name: "Note : 5 sur 5" })).toBeVisible();
  });
});
