/**
 * Cleans raw text extracted from a PDF for display in the chat.
 *
 * Drops page headers, collapses runs of blank lines and dot leaders, and
 * rejoins a métré calculation the extractor split over three lines: `2f4,60`,
 * `=`, `9,200` becomes `2f4,60 = 9,200`. A standalone `=` followed by a number
 * is a subtotal, attached to the previous line instead.
 */
export function cleanText(raw: string): string {
  const lines = raw.split("\n").map((l) => l.trimEnd());

  const cleaned: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (!line) {
      if (cleaned.length > 0 && cleaned[cleaned.length - 1] !== "") {
        cleaned.push("");
      }
      i++;
      continue;
    }

    if (/^Page\s+\d+/i.test(line)) {
      i++;
      continue;
    }

    if (
      i + 2 < lines.length &&
      lines[i + 1].trim() === "=" &&
      /^[\d,.]+/.test(lines[i + 2].trim())
    ) {
      const value = lines[i + 2].trim().replace(/\s*\.{2,}.*$/, "");
      cleaned.push(`${line} = ${value}`);
      i += 3;
      continue;
    }

    if (
      line === "=" &&
      i + 1 < lines.length &&
      /^[\d,.]+/.test(lines[i + 1].trim())
    ) {
      const value = lines[i + 1].trim().replace(/\s*\.{2,}.*$/, "");
      if (cleaned.length > 0 && cleaned[cleaned.length - 1] !== "") {
        cleaned[cleaned.length - 1] += `  →  ${value}`;
      } else {
        cleaned.push(`= ${value}`);
      }
      i += 2;
      continue;
    }

    const cleanedLine = line
      .replace(/\s*\.{3,}\s*/g, " ")
      .replace(/\s{3,}/g, "  ")
      .trimEnd();

    cleaned.push(cleanedLine);
    i++;
  }

  return cleaned
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
