import { ChevronDown, ChevronUp } from "lucide-react";
import type { SortDirection, SortField } from "../utils/documentDisplay";

interface DocumentListSortableHeaderProps {
  label: string;
  field: SortField;
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
}

/** One sortable column header for `DocumentList`'s table. */
export function DocumentListSortableHeader({
  label,
  field,
  sortField,
  sortDirection,
  onSort,
}: DocumentListSortableHeaderProps): React.ReactElement {
  const isActive = sortField === field;
  return (
    <th className="py-3 pr-4 font-medium">
      <button
        type="button"
        className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))] transition-colors"
        onClick={() => onSort(field)}
      >
        {label}
        {isActive ? (
          sortDirection === "asc" ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )
        ) : (
          <ChevronDown className="h-3.5 w-3.5 opacity-30" />
        )}
      </button>
    </th>
  );
}
