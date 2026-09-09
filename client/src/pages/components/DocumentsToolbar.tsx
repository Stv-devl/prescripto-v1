import { FolderPlus, LayoutGrid, LayoutList, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";

type ViewMode = "list" | "grid";

interface DocumentsToolbarProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  search: string;
  onSearchChange: (value: string) => void;
  canCreateFolder: boolean;
  onShowCreateFolder: () => void;
  summary: string | null;
}

export function DocumentsToolbar({
  viewMode,
  onViewModeChange,
  search,
  onSearchChange,
  canCreateFolder,
  onShowCreateFolder,
  summary,
}: DocumentsToolbarProps) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          className={`h-8 w-8 ${viewMode === "list" ? "text-[#FFC300]" : "text-muted-foreground"}`}
          onClick={() => onViewModeChange("list")}
          aria-label="Vue liste"
        >
          <LayoutList className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={`h-8 w-8 ${viewMode === "grid" ? "text-[#FFC300]" : "text-muted-foreground"}`}
          onClick={() => onViewModeChange("grid")}
          aria-label="Vue grille"
        >
          <LayoutGrid className="h-4 w-4" />
        </Button>
      </div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Rechercher…"
          className="h-8 w-48 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] pl-8 pr-3 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
        />
      </div>
      {canCreateFolder && (
        <Button variant="outline" size="sm" onClick={onShowCreateFolder}>
          <FolderPlus className="mr-1.5 h-4 w-4" />
          Nouveau dossier
        </Button>
      )}
      <p className="ml-auto text-sm text-muted-foreground">{summary}</p>
    </div>
  );
}
