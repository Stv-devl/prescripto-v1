import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import { unwrap } from "@/lib/result";
import {
  getSummary,
  getSummaryStatus,
  streamSummary,
} from "../services/summary.service";
import type { ProjectSummaryData, SummaryProgressEvent } from "../types/types";

/** Check whether the project has documents and/or a cached summary. */
export function useSummaryStatus(projectId: string) {
  return useQuery({
    queryKey: ["summary-status", projectId],
    queryFn: async () => unwrap(await getSummaryStatus(projectId)),
  });
}

/** Fetch the cached project summary (only when status says it exists). */
export function useSummary(projectId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["summary", projectId],
    queryFn: async () => unwrap(await getSummary(projectId)),
    enabled,
  });
}

interface SummaryGenerationState {
  progress: SummaryProgressEvent[];
  isGenerating: boolean;
  generatedData: ProjectSummaryData | null;
  finalStatus: string | null;
  error: string | null;
  generate: () => Promise<void>;
}

/** Drives summary generation and exposes what the stream reports. */
export function useSummaryGeneration(
  projectId: string,
): SummaryGenerationState {
  const [progress, setProgress] = useState<SummaryProgressEvent[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedData, setGeneratedData] = useState<ProjectSummaryData | null>(
    null,
  );
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const generate = useCallback(async () => {
    setProgress([]);
    setIsGenerating(true);
    setGeneratedData(null);
    setFinalStatus(null);
    setError(null);

    try {
      for await (const event of streamSummary(projectId)) {
        if (event.type === "progress") {
          setProgress((previous) => [...previous, event]);
        } else if (event.type === "complete") {
          setGeneratedData(event.summary);
          setFinalStatus(event.status);
        } else {
          setError(event.message);
        }
      }

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["summary", projectId] }),
        queryClient.invalidateQueries({
          queryKey: ["summary-status", projectId],
        }),
      ]);
    } catch (cause) {
      console.error("Summary generation failed:", cause);
      setError("Erreur lors de la génération du résumé.");
    } finally {
      setIsGenerating(false);
    }
  }, [projectId, queryClient]);

  return {
    progress,
    isGenerating,
    generatedData,
    finalStatus,
    error,
    generate,
  };
}
