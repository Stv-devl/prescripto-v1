import { describe, expect, it } from "vitest";
import type { ChunkListItem } from "../types/types";
import { findOverlap, hasGap } from "./chunkGapOverlap.utils";

function buildChunk(overrides: Partial<ChunkListItem>): ChunkListItem {
  return {
    id: "chunk-1",
    document_id: "doc-1",
    filename: "cctp-lot-01.pdf",
    text_preview: "Preview text",
    page: 1,
    position: 1,
    char_count: 500,
    content_type: "text",
    keywords: null,
    section_title: null,
    parent_sections: null,
    lot: "lot-01",
    phase: "conception",
    type: "cctp",
    qdrant_point_id: "qdrant-point-1",
    created_at: "2026-01-01T00:00:00Z",
    quality_score: 0.9,
    ...overrides,
  };
}

describe("hasGap", () => {
  it("detects a gap when the position jumps by more than 1 (same page)", () => {
    const previous = buildChunk({ position: 2, page: 3 });
    const current = buildChunk({ position: 5, page: 3 });

    expect(hasGap(current, previous)).toBe(true);
  });

  it("detects a gap when the page jumps by more than 1 (contiguous position)", () => {
    const previous = buildChunk({ position: 5, page: 2 });
    const current = buildChunk({ position: 6, page: 10 });

    expect(hasGap(current, previous)).toBe(true);
  });

  it("does not detect a gap for two contiguous chunks (position+1, same page)", () => {
    const previous = buildChunk({ position: 3, page: 2 });
    const current = buildChunk({ position: 4, page: 2 });

    expect(hasGap(current, previous)).toBe(false);
  });
});

describe("findOverlap", () => {
  it("keeps the longest match when a shorter valid overlap (>=20 chars) also exists at the same boundary", () => {
    // pattern has period 20, so overlap45's first 25 chars equal its last 25
    // chars: both a length-25 and a length-45 boundary match exist here.
    const pattern = "ABCDEFGHIJKLMNOPQRST";
    const overlap45 = pattern + pattern + pattern.slice(0, 5);

    const textA = "prefix-content-not-matching#" + overlap45;
    const textB = overlap45 + "@suffix-content-not-matching";

    const result = findOverlap(textA, textB);

    expect(result).toBe(overlap45);
    expect(result.length).toBe(45);
  });

  it("returns an empty string when the only possible overlap is under 20 characters", () => {
    // 14 distinct characters: below the 20-char minimum candidate length.
    const shortOverlap = "QWERTYUIOPASDF";

    const textA = "Alpha section unique content*" + shortOverlap;
    const textB = shortOverlap + "^Beta section unique content";

    expect(findOverlap(textA, textB)).toBe("");
  });

  it("returns an empty string when there is no overlap at all", () => {
    const textA =
      "This is the first uploaded document, ending without any shared content.";
    const textB =
      "A completely different second document begins here with unrelated words.";

    expect(findOverlap(textA, textB)).toBe("");
  });

  it("with a maxCheck smaller than the real overlap, only returns what maxCheck allows from each end", () => {
    const textA = "B".repeat(60);
    const textB = "B".repeat(60);

    const result = findOverlap(textA, textB, 30);

    expect(result).toBe("B".repeat(30));
    expect(result.length).toBe(30);
  });

  it("defaults to a maxCheck of 400 when none is provided", () => {
    const textA = "A".repeat(450);
    const textB = "A".repeat(450);

    const result = findOverlap(textA, textB);

    expect(result).toBe("A".repeat(400));
    expect(result.length).toBe(400);
  });
});
