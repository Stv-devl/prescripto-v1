import { useMemo } from "react";
import type { Document } from "@/features/projects";
import { formatSize } from "@/lib/utils";

/** "N documents — M en traitement — K erreurs — taille totale", or null when empty. */
export function useDocumentsSummary(documents: Document[] | undefined): string | null {
  return useMemo(() => {
    if (!documents || documents.length === 0) return null;

    const processing = documents.filter(
      (d) => d.status === "processing" || d.status === "uploading",
    ).length;
    const errors = documents.filter((d) => d.status === "error").length;
    const totalSize = documents.reduce((sum, d) => sum + d.size, 0);

    const parts: string[] = [
      `${documents.length} document${documents.length > 1 ? "s" : ""}`,
    ];
    if (processing > 0) parts.push(`${processing} en traitement`);
    if (errors > 0) parts.push(`${errors} erreur${errors > 1 ? "s" : ""}`);
    parts.push(formatSize(totalSize));

    return parts.join(" — ");
  }, [documents]);
}
