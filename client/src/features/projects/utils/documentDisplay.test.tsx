import { render } from "@testing-library/react";
import {
  File as FileIcon,
  FileImage,
  FileSpreadsheet,
  FileText,
  Pencil,
} from "lucide-react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProcessingProgress, createDragGhost, getFileIcon } from "./documentDisplay";

const START = new Date("2026-09-01T12:00:00Z");

function renderAfter(seconds: number): ReturnType<typeof render> {
  vi.setSystemTime(new Date(START.getTime() + seconds * 1000));
  return render(<ProcessingProgress startedAt={START.toISOString()} />);
}

describe("getFileIcon", () => {
  it("maps pdf to the document icon in red", () => {
    expect(getFileIcon("plan.pdf")).toEqual({
      icon: FileText,
      colorClass: "text-red-400",
    });
  });

  it("maps docx to the document icon in blue", () => {
    expect(getFileIcon("cctp.docx")).toEqual({
      icon: FileText,
      colorClass: "text-blue-400",
    });
  });

  it("maps doc to the document icon in blue", () => {
    expect(getFileIcon("cctp.doc")).toEqual({
      icon: FileText,
      colorClass: "text-blue-400",
    });
  });

  it("maps xlsx to the spreadsheet icon in green", () => {
    expect(getFileIcon("metre.xlsx")).toEqual({
      icon: FileSpreadsheet,
      colorClass: "text-green-400",
    });
  });

  it("maps xls to the spreadsheet icon in green", () => {
    expect(getFileIcon("metre.xls")).toEqual({
      icon: FileSpreadsheet,
      colorClass: "text-green-400",
    });
  });

  it("maps dwg to the drawing icon in orange", () => {
    expect(getFileIcon("coupe.dwg")).toEqual({
      icon: Pencil,
      colorClass: "text-orange-400",
    });
  });

  it("maps dxf to the drawing icon in orange", () => {
    expect(getFileIcon("coupe.dxf")).toEqual({
      icon: Pencil,
      colorClass: "text-orange-400",
    });
  });

  it("maps every image extension to the image icon in purple", () => {
    for (const name of ["a.png", "a.jpg", "a.jpeg", "a.webp"]) {
      expect(getFileIcon(name)).toEqual({
        icon: FileImage,
        colorClass: "text-purple-400",
      });
    }
  });

  it("compares the extension in lower case", () => {
    expect(getFileIcon("PLAN.PDF")).toEqual({
      icon: FileText,
      colorClass: "text-red-400",
    });
  });

  it("falls back to the generic icon for an unknown extension", () => {
    expect(getFileIcon("archive.zip")).toEqual({
      icon: FileIcon,
      colorClass: "text-muted-foreground",
    });
  });

  it("falls back to the generic icon for a name with no extension", () => {
    expect(getFileIcon("README")).toEqual({
      icon: FileIcon,
      colorClass: "text-muted-foreground",
    });
  });
});

describe("createDragGhost", () => {
  it("inserts an element carrying the filename, positioned off screen", () => {
    const ghost = createDragGhost("plan.pdf");

    expect(document.body.contains(ghost)).toBe(true);
    expect(ghost.textContent).toBe("plan.pdf");
    expect(ghost.style.position).toBe("fixed");
    expect(ghost.style.top).toBe("-1000px");
    expect(ghost.style.left).toBe("-1000px");

    ghost.remove();
  });
});

describe("ProcessingProgress", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the step matching the elapsed time", () => {
    vi.useFakeTimers();

    const cases: [number, string][] = [
      [0, "Extraction…"],
      [7, "Extraction…"],
      [8, "Nettoyage…"],
      [11, "Nettoyage…"],
      [12, "Classification…"],
      [17, "Classification…"],
      [18, "Découpage…"],
      [22, "Découpage…"],
      [23, "Indexation…"],
      [29, "Indexation…"],
    ];

    for (const [elapsed, label] of cases) {
      const { container, unmount } = renderAfter(elapsed);
      expect(container.textContent).toBe(label);
      unmount();
    }
  });

  it("caps the progress bar at 95 percent past the last step", () => {
    vi.useFakeTimers();

    const { container } = renderAfter(120);
    const bar = container.querySelector<HTMLDivElement>("div[style]");

    expect(bar?.style.width).toBe("95%");
  });

  it("grows the progress bar proportionally to the elapsed time", () => {
    vi.useFakeTimers();

    const { container } = renderAfter(15);
    const bar = container.querySelector<HTMLDivElement>("div[style]");

    expect(bar?.style.width).toBe("48%");
  });

  it("releases its interval on unmount", () => {
    vi.useFakeTimers();

    const { unmount } = renderAfter(3);
    expect(vi.getTimerCount()).toBe(1);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
