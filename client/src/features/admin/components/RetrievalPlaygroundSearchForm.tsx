import { Search } from "lucide-react";

interface RetrievalPlaygroundSearchFormProps {
  query: string;
  onQueryChange: (value: string) => void;
  lot: string;
  onLotChange: (value: string) => void;
  contentType: string;
  onContentTypeChange: (value: string) => void;
  lots: string[];
  contentTypes: string[];
  isPending: boolean;
  onSearch: () => void;
}

/** The playground's controlled search form: query text, lot/content-type filters, submit. */
export function RetrievalPlaygroundSearchForm({
  query,
  onQueryChange,
  lot,
  onLotChange,
  contentType,
  onContentTypeChange,
  lots,
  contentTypes,
  isPending,
  onSearch,
}: RetrievalPlaygroundSearchFormProps) {
  return (
    <section className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[hsl(var(--foreground))]">
        <Search className="h-4 w-4 text-[#FFC300]" />
        Test de retrieval sémantique
      </h2>

      <div className="space-y-3">
        <textarea
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Tapez une question comme un utilisateur le ferait... (ex: Quelle épaisseur d'isolation pour les murs extérieurs ?)"
          rows={3}
          className="w-full resize-none rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSearch();
            }
          }}
        />

        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-[hsl(var(--muted-foreground))]">
              Lot
              <select
                value={lot}
                onChange={(e) => onLotChange(e.target.value)}
                className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              >
                <option value="">Tous les lots</option>
                {lots.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-[hsl(var(--muted-foreground))]">
              Content type
              <select
                value={contentType}
                onChange={(e) => onContentTypeChange(e.target.value)}
                className="mt-1 w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              >
                <option value="">Tous les types</option>
                {contentTypes.map((ct) => (
                  <option key={ct} value={ct}>{ct}</option>
                ))}
              </select>
            </label>
          </div>

          <button
            onClick={onSearch}
            disabled={!query.trim() || isPending}
            className="flex items-center gap-2 rounded-md bg-[#FFC300] px-5 py-2 text-sm font-medium text-[#1C1C1C] transition-colors hover:bg-[#FFC300]/90 disabled:opacity-50"
          >
            {isPending ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#1C1C1C] border-t-transparent" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Rechercher
          </button>
        </div>
      </div>
    </section>
  );
}
