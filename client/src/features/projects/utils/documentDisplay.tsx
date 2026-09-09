import {
  Loader2,
  FileText,
  FileSpreadsheet,
  FileImage,
  Pencil,
  File,
} from "lucide-react";
import { useEffect, useState } from "react";

// --- Sort types ---

export type SortField =
  | "filename"
  | "type"
  | "lot"
  | "phase"
  | "size"
  | "status"
  | "created_at";
export type SortDirection = "asc" | "desc";

// --- Status maps ---

export const STATUS_STYLES: Record<string, string> = {
  ready: "bg-green-900/40 text-green-400 border-green-700/40",
  processing: "bg-yellow-900/40 text-yellow-400 border-yellow-700/40",
  uploading: "bg-blue-900/40 text-blue-400 border-blue-700/40",
  error: "bg-red-900/40 text-red-400 border-red-700/40",
};

export const STATUS_LABELS: Record<string, string> = {
  ready: "Prêt",
  processing: "Traitement…",
  uploading: "Envoi…",
  error: "Erreur",
};

// --- File icon helper ---

/** Returns the appropriate Lucide icon and color class for a given filename extension. */
export function getFileIcon(filename: string): {
  icon: typeof File;
  colorClass: string;
} {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";

  switch (ext) {
    case "pdf":
      return { icon: FileText, colorClass: "text-red-400" };
    case "docx":
    case "doc":
      return { icon: FileText, colorClass: "text-blue-400" };
    case "xlsx":
    case "xls":
      return { icon: FileSpreadsheet, colorClass: "text-green-400" };
    case "dwg":
    case "dxf":
      return { icon: Pencil, colorClass: "text-orange-400" };
    case "png":
    case "jpg":
    case "jpeg":
    case "webp":
      return { icon: FileImage, colorClass: "text-purple-400" };
    default:
      return { icon: File, colorClass: "text-muted-foreground" };
  }
}

// --- Processing progress (simulated) ---

const PIPELINE_STEPS = [
  { label: "Extraction", duration: 8 },
  { label: "Nettoyage", duration: 4 },
  { label: "Classification", duration: 6 },
  { label: "Découpage", duration: 5 },
  { label: "Indexation", duration: 7 },
] as const;

const TOTAL_DURATION = PIPELINE_STEPS.reduce((sum, s) => sum + s.duration, 0);

/** Displays a simulated processing progress bar. */
export function ProcessingProgress({
  startedAt,
}: {
  startedAt: string;
}): React.ReactElement {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = new Date(startedAt).getTime();
    const tick = (): void =>
      setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  let cumulated = 0;
  let currentStep = PIPELINE_STEPS[PIPELINE_STEPS.length - 1].label;
  for (const step of PIPELINE_STEPS) {
    cumulated += step.duration;
    if (elapsed < cumulated) {
      currentStep = step.label;
      break;
    }
  }

  const progress = Math.min(Math.round((elapsed / TOTAL_DURATION) * 95), 95);

  return (
    <div className="flex flex-col gap-1 max-w-[120px]">
      <span className="inline-flex items-center gap-1.5 text-xs text-yellow-400">
        <Loader2 className="h-3 w-3 animate-spin shrink-0" />
        {currentStep}…
      </span>
      <div className="h-1 w-full overflow-hidden rounded-full bg-yellow-900/30">
        <div
          className="h-full rounded-full bg-yellow-400 transition-[width] duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

// --- Custom drag ghost helper ---

export function createDragGhost(filename: string): HTMLElement {
  const ghost = document.createElement("div");
  ghost.className =
    "flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-3 py-2 text-sm font-medium shadow-lg";
  ghost.textContent = filename;
  ghost.style.position = "fixed";
  ghost.style.top = "-1000px";
  ghost.style.left = "-1000px";
  ghost.style.zIndex = "9999";
  document.body.appendChild(ghost);
  return ghost;
}
