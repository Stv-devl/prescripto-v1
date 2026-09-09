import { FolderTree, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useAdminStore } from "../stores/store";
import type { ChunkStatsResponse } from "../types/types";
import { SectionTree } from "./SectionTree";

interface ChunkFiltersProps {
  stats: ChunkStatsResponse | undefined;
  projectId: string;
}

const inputClass =
  "rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]";

export function ChunkFilters({ stats, projectId }: ChunkFiltersProps) {
  const { filters, setFilter, resetFilters } = useAdminStore();
  const [searchInput, setSearchInput] = useState(filters.search ?? "");
  const [showSectionTree, setShowSectionTree] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchInput !== (filters.search ?? "")) {
        setFilter("search", searchInput || undefined);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, filters.search, setFilter]);

  const lots = stats ? Object.keys(stats.by_lot).sort() : [];
  const types = stats ? Object.keys(stats.by_type).sort() : [];
  const contentTypes = stats ? Object.keys(stats.by_content_type).sort() : [];

  const hasActiveFilters =
    filters.lot || filters.type || filters.content_type ||
    filters.min_chars !== undefined || filters.max_chars !== undefined ||
    filters.has_keywords !== undefined || filters.search ||
    filters.orphan !== undefined || filters.parent_section;

  function handleReset(): void {
    resetFilters();
    setSearchInput("");
  }

  function handleSectionSelect(section: string): void {
    setFilter("parent_section", section);
    setShowSectionTree(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-4">
        {/* Search */}
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
          <input
            type="text"
            placeholder="Rechercher dans le texte..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className={`${inputClass} w-full pl-9`}
          />
        </div>

        <select
          value={filters.lot ?? ""}
          onChange={(e) => setFilter("lot", e.target.value || undefined)}
          className={inputClass}
        >
          <option value="">Tous les lots</option>
          {lots.map((lot) => (
            <option key={lot} value={lot}>{lot}</option>
          ))}
        </select>

        <select
          value={filters.type ?? ""}
          onChange={(e) => setFilter("type", e.target.value || undefined)}
          className={inputClass}
        >
          <option value="">Tous les types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        <select
          value={filters.content_type ?? ""}
          onChange={(e) => setFilter("content_type", e.target.value || undefined)}
          className={inputClass}
        >
          <option value="">Tous content_types</option>
          {contentTypes.map((ct) => (
            <option key={ct} value={ct}>{ct}</option>
          ))}
        </select>

        <input
          type="number"
          placeholder="Min chars"
          value={filters.min_chars ?? ""}
          onChange={(e) =>
            setFilter("min_chars", e.target.value ? Number(e.target.value) : undefined)
          }
          className={`${inputClass} w-24`}
        />
        <input
          type="number"
          placeholder="Max chars"
          value={filters.max_chars ?? ""}
          onChange={(e) =>
            setFilter("max_chars", e.target.value ? Number(e.target.value) : undefined)
          }
          className={`${inputClass} w-24`}
        />

        <select
          value={filters.has_keywords === undefined ? "" : String(filters.has_keywords)}
          onChange={(e) => {
            const v = e.target.value;
            setFilter("has_keywords", v === "" ? undefined : v === "true");
          }}
          className={inputClass}
        >
          <option value="">Keywords: tous</option>
          <option value="true">Avec keywords</option>
          <option value="false">Sans keywords</option>
        </select>

        {/* Orphan filter */}
        <label className="flex items-center gap-1.5 text-sm text-[hsl(var(--muted-foreground))]">
          <input
            type="checkbox"
            checked={filters.orphan === true}
            onChange={(e) => setFilter("orphan", e.target.checked ? true : undefined)}
            className="h-4 w-4 rounded border-[hsl(var(--border))] accent-[#FFC300]"
          />
          Orphelins
        </label>

        {/* Section tree toggle */}
        <button
          onClick={() => setShowSectionTree(!showSectionTree)}
          className={`flex items-center gap-1.5 ${inputClass} ${
            filters.parent_section ? "border-[#FFC300] text-[#FFC300]" : ""
          }`}
        >
          <FolderTree className="h-3.5 w-3.5" />
          {filters.parent_section ? filters.parent_section : "Section"}
        </button>

        {filters.parent_section && (
          <button
            onClick={() => setFilter("parent_section", undefined)}
            className="rounded-full bg-[#FFC300]/15 px-2 py-0.5 text-xs text-[#FFC300] hover:bg-[#FFC300]/25"
          >
            {filters.parent_section} <X className="ml-1 inline h-3 w-3" />
          </button>
        )}

        {hasActiveFilters && (
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 rounded-md bg-[hsl(var(--muted))] px-3 py-2 text-sm font-medium text-[hsl(var(--foreground))] transition-colors hover:bg-[hsl(var(--muted))]/80"
          >
            <X className="h-3.5 w-3.5" />
            Réinitialiser
          </button>
        )}
      </div>

      {/* Section tree panel */}
      {showSectionTree && (
        <div className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-4">
          <SectionTree projectId={projectId} onSelect={handleSectionSelect} />
        </div>
      )}
    </div>
  );
}
