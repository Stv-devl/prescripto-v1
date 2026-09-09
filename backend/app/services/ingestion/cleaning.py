"""Post-extraction cleaning: remove headers, footers, and TOC from pages."""

import re
from collections import Counter

from app.services.ingestion.extraction import ExtractedPage

_SCAN_LINES = 5

_MIN_RATIO = 0.5

_MIN_PAGES = 3

_TOC_LINE_RE = re.compile(r"^.+\.{3,}\s*\d+\s*$")

_TOC_PAGE_RATIO = 0.6


def _normalize(line: str) -> str:
    """Normalize a line for comparison: strip whitespace, replace page numbers."""
    s = line.strip()
    s = re.sub(r"\bpage\s*\d+\s*/\s*\d+", "PAGE_NUM", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpage\s*\d+", "PAGE_NUM", s, flags=re.IGNORECASE)
    s = re.sub(r"^\d+$", "PAGE_NUM", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_toc_line(line: str) -> bool:
    """Check if a line looks like a table-of-contents entry."""
    return bool(_TOC_LINE_RE.match(line.strip()))


def strip_toc_pages(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Remove full TOC pages and individual TOC lines from remaining pages."""
    cleaned: list[ExtractedPage] = []

    for page in pages:
        lines = page.text.split("\n")
        non_empty = [line for line in lines if line.strip()]

        if not non_empty:
            continue

        toc_count = sum(1 for line in non_empty if _is_toc_line(line))
        toc_ratio = toc_count / len(non_empty)

        if toc_ratio >= _TOC_PAGE_RATIO:
            continue

        if toc_count > 0:
            filtered = [line for line in lines if not _is_toc_line(line)]
            text = re.sub(r"\n{3,}", "\n\n", "\n".join(filtered)).strip()
            if text:
                cleaned.append(ExtractedPage(text=text, page=page.page, source=page.source))
        else:
            cleaned.append(page)

    return cleaned


def strip_headers_footers(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Remove repetitive header/footer lines from extracted pages.

    Detects lines that appear at the top or bottom of many pages and strips them.
    Works generically for any document type.
    """
    if len(pages) < _MIN_PAGES:
        return pages

    threshold = int(len(pages) * _MIN_RATIO)

    top_counter: Counter[str] = Counter()
    bottom_counter: Counter[str] = Counter()

    for page in pages:
        lines = page.text.split("\n")
        non_empty = [line for line in lines if line.strip()]

        top_lines = non_empty[:_SCAN_LINES]
        bottom_lines = non_empty[-_SCAN_LINES:] if len(non_empty) > _SCAN_LINES else []

        for norm in {_normalize(line) for line in top_lines}:
            if norm:
                top_counter[norm] += 1

        for norm in {_normalize(line) for line in bottom_lines}:
            if norm:
                bottom_counter[norm] += 1

    repeated = set()
    for norm, count in top_counter.items():
        if count >= threshold and norm != "PAGE_NUM":
            repeated.add(norm)
    for norm, count in bottom_counter.items():
        if count >= threshold and norm != "PAGE_NUM":
            repeated.add(norm)

    repeated.add("PAGE_NUM")

    if not repeated:
        return pages

    cleaned: list[ExtractedPage] = []
    for page in pages:
        lines = page.text.split("\n")
        filtered = [line for line in lines if _normalize(line) not in repeated]

        text = re.sub(r"\n{3,}", "\n\n", "\n".join(filtered)).strip()
        if text:
            cleaned.append(ExtractedPage(text=text, page=page.page, source=page.source))

    return cleaned


_MIN_PAGE_CHARS = 50


def strip_sparse_pages(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Remove pages with very little content (cover pages, near-empty residuals)."""
    return [p for p in pages if len(p.text.strip()) >= _MIN_PAGE_CHARS]


def clean_pages(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Run all cleaning steps in order."""
    pages = strip_toc_pages(pages)
    pages = strip_headers_footers(pages)
    pages = strip_sparse_pages(pages)
    return pages
