import { describe, expect, it } from "vitest";
import { cleanText } from "./textCleaning";

describe("cleanText", () => {
  it("keeps plain text and drops trailing whitespace", () => {
    expect(cleanText("Bonjour   \nMonde  ")).toBe("Bonjour\nMonde");
  });

  it("drops page header lines", () => {
    expect(cleanText("Avant\nPage 12\nApres")).toBe("Avant\nApres");
  });

  it("merges a three-line calculation into a single line", () => {
    expect(cleanText("2f4,60\n=\n9,200")).toBe("2f4,60 = 9,200");
  });

  it("attaches a standalone equals sign to the previous line as a subtotal", () => {
    expect(cleanText("Total\nPage 1\n=\n1,50")).toBe("Total  →  1,50");
  });

  it("collapses dot leaders into a single space", () => {
    expect(cleanText("Cloison .......... m3")).toBe("Cloison m3");
  });

  it("collapses three or more blank lines into one", () => {
    expect(cleanText("A\n\n\n\n\nB")).toBe("A\n\nB");
  });

  it("truncates whatever follows the dot leaders in a merged value", () => {
    expect(cleanText("2f4,60\n=\n9,200 .... m3")).toBe("2f4,60 = 9,200");
  });

  it("truncates the dot leaders in a subtotal attached to the previous line", () => {
    expect(cleanText("Total\nPage 1\n=\n1,50 .... m3")).toBe("Total  →  1,50");
  });

  it("returns an empty string for an empty input", () => {
    expect(cleanText("")).toBe("");
  });

  it("returns an empty string for an input made only of blank lines", () => {
    expect(cleanText("\n\n\n")).toBe("");
  });

  it("keeps the equals sign inline when there is no previous line to attach to", () => {
    expect(cleanText("=\n1,50")).toBe("= 1,50");
  });
});
