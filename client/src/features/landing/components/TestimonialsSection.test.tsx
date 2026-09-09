import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Testimonial } from "../types/types";
import { TestimonialCard } from "./TestimonialsSection";

const THREE_OUT_OF_FIVE: Testimonial = {
  name: "Claire Morel",
  role: "Économiste de la construction",
  quote: "Bonne base, il manque encore quelques lots.",
  image: "/pexels-olly-774909.webp",
  rating: 3,
};

describe("TestimonialCard — the rating shown is the rating given", () => {
  it("renders three filled marks and two empty ones for a testimonial rated three", () => {
    const { container } = render(
      <TestimonialCard
        testimonial={THREE_OUT_OF_FIVE}
        isActive
        position={0}
      />,
    );

    expect(container.querySelectorAll('[data-filled="true"]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-filled="false"]')).toHaveLength(2);
    expect(screen.getByRole("img", { name: "Note : 3 sur 5" })).toBeVisible();
  });

  it("keeps a card that is not the active one out of the accessibility tree", () => {
    render(
      <TestimonialCard
        testimonial={THREE_OUT_OF_FIVE}
        isActive={false}
        position={1}
      />,
    );

    expect(screen.queryByRole("img", { name: /Note/ })).not.toBeInTheDocument();
  });
});
