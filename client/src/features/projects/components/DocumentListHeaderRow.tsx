import { Checkbox } from "@/components/ui/Checkbox";
import type { SortDirection, SortField } from "../utils/documentDisplay";
import { DocumentListSortableHeader } from "./DocumentListSortableHeader";

interface DocumentListHeaderRowProps {
  hasSelection: boolean;
  allSelected: boolean;
  partiallySelected: boolean;
  docIds: string[];
  onToggleSelectAll?: (allIds: string[]) => void;
  sortField: SortField;
  sortDirection: SortDirection;
  onSort: (field: SortField) => void;
}

/** `DocumentList`'s table header row: the select-all checkbox and its 7 sortable columns. */
export function DocumentListHeaderRow({
  hasSelection,
  allSelected,
  partiallySelected,
  docIds,
  onToggleSelectAll,
  sortField,
  sortDirection,
  onSort,
}: DocumentListHeaderRowProps): React.ReactElement {
  return (
    <tr className="border-b border-[hsl(var(--border))] text-left text-muted-foreground">
      {hasSelection && (
        <th className="w-10 py-3 pr-2">
          <Checkbox
            checked={allSelected}
            indeterminate={partiallySelected}
            onChange={() => onToggleSelectAll?.(docIds)}
            aria-label="Tout sélectionner"
            onClick={(e) => e.stopPropagation()}
          />
        </th>
      )}
      <DocumentListSortableHeader label="Fichier" field="filename" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Type" field="type" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Lot" field="lot" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Phase" field="phase" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Taille" field="size" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Statut" field="status" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <DocumentListSortableHeader label="Date" field="created_at" sortField={sortField} sortDirection={sortDirection} onSort={onSort} />
      <th className="py-3 font-medium">
        <span className="sr-only">Actions</span>
      </th>
    </tr>
  );
}
