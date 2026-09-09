import { ArrowLeft, ChevronRight } from "lucide-react";
import type { Folder } from "@/features/projects";

interface FolderBreadcrumbProps {
  folder: Folder;
  documentCount: number;
  onBack: () => void;
}

export function FolderBreadcrumb({
  folder,
  documentCount,
  onBack,
}: FolderBreadcrumbProps) {
  return (
    <nav className="mb-4 flex items-center gap-2 text-sm">
      <button
        type="button"
        onClick={onBack}
        className="group inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
      >
        <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
        Documents
      </button>
      <ChevronRight className="h-4 w-4 text-muted-foreground" />
      <span className="font-medium text-[hsl(var(--foreground))]">
        {folder.name}
        <span className="ml-1.5 text-muted-foreground font-normal">
          ({documentCount} doc{documentCount !== 1 ? "s" : ""})
        </span>
      </span>
    </nav>
  );
}
