import { ChevronDown, ChevronRight, FolderTree } from "lucide-react";
import { useState } from "react";
import { ErrorMessage } from "@/components/feedback/ErrorMessage";
import { Skeleton } from "@/components/feedback/Skeleton";
import { useSectionTree } from "../hooks/hooks";
import type { SectionNode } from "../types/types";

interface SectionTreeProps {
  projectId: string;
  onSelect: (section: string) => void;
}

export function SectionTree({ projectId, onSelect }: SectionTreeProps) {
  const { data: tree, isPending, error } = useSectionTree(projectId);

  if (isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} variant="text" />
        ))}
      </div>
    );
  }

  if (error && !tree) {
    return <ErrorMessage error={error} inline />;
  }

  if (!tree || tree.length === 0) {
    return (
      <div className="space-y-1">
        {error && <ErrorMessage error={error} inline />}
        {!error && (
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Aucune section trouvée.</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {error && <ErrorMessage error={error} inline />}
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-[hsl(var(--foreground))]">
        <FolderTree className="h-3.5 w-3.5 text-[#FFC300]" />
        Sections
      </h2>
      {tree.map((node) => (
        <TreeNode key={node.title} node={node} depth={0} onSelect={onSelect} />
      ))}
    </div>
  );
}

interface TreeNodeProps {
  node: SectionNode;
  depth: number;
  onSelect: (section: string) => void;
}

function TreeNode({ node, depth, onSelect }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) setExpanded(!expanded);
          onSelect(node.title);
        }}
        aria-expanded={hasChildren ? expanded : undefined}
        className="flex w-full items-center gap-1 rounded px-1.5 py-1 text-left text-xs transition-colors hover:bg-[hsl(var(--muted))]"
        style={{ paddingLeft: `${depth * 16 + 4}px` }}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-[hsl(var(--muted-foreground))]" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-[hsl(var(--muted-foreground))]" />
          )
        ) : (
          <span className="w-3" />
        )}
        <span className="flex-1 truncate text-[hsl(var(--foreground))]">{node.title}</span>
        <span className="shrink-0 text-[hsl(var(--muted-foreground))]">
          {node.chunk_count}
        </span>
      </button>
      {expanded &&
        hasChildren &&
        node.children.map((child) => (
          <TreeNode key={child.title} node={child} depth={depth + 1} onSelect={onSelect} />
        ))}
    </div>
  );
}
