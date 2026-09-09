import {
  Landmark,
  LayoutGrid,
  Fence,
  Layers,
  Footprints,
  Home,
  DoorOpen,
  Flame,
} from "lucide-react";
import type { SystemeConstructifItem } from "../types/types";

/** Map constructif labels → icons for the left gutter. */
const CONSTRUCTIF_ICONS: Record<string, React.ReactNode> = {
  "Terrain et sol": <Landmark className="h-3.5 w-3.5" />,
  "Sol & Fondations": <Landmark className="h-3.5 w-3.5" />,
  Infrastructure: <LayoutGrid className="h-3.5 w-3.5" />,
  Dallage: <LayoutGrid className="h-3.5 w-3.5" />,
  Élévation: <Fence className="h-3.5 w-3.5" />,
  "Élévation (Murs)": <Fence className="h-3.5 w-3.5" />,
  Planchers: <Layers className="h-3.5 w-3.5" />,
  "Revêtement de sol": <Footprints className="h-3.5 w-3.5" />,
  "Charpente & Couverture": <Home className="h-3.5 w-3.5" />,
  "Menuiseries extérieures": <DoorOpen className="h-3.5 w-3.5" />,
  "Chauffage & ECS": <Flame className="h-3.5 w-3.5" />,
};

interface ProjectSummaryTabConstructifEntryProps {
  item: SystemeConstructifItem;
  index: number;
}

/** One structural-system entry of the project summary report. */
export function ProjectSummaryTabConstructifEntry({
  item,
  index,
}: ProjectSummaryTabConstructifEntryProps): React.ReactElement {
  const icon = CONSTRUCTIF_ICONS[item.label];

  return (
    <div className="py-5">
      {/* Header: icon + label */}
      <div className="flex items-center gap-2.5 mb-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[#FFC300]/30 bg-[#FFC300]/8 text-[#FFC300]">
          {icon ?? (
            <span className="text-[10px] font-bold leading-none">
              {String(index + 1).padStart(2, "0")}
            </span>
          )}
        </span>
        <dt className="text-[13px] font-semibold text-[hsl(var(--foreground))] tracking-tight">
          {item.label}
        </dt>
      </div>

      {/* KPI badges */}
      {item.kpis.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {item.kpis.map((kpi) => (
            <span
              key={kpi}
              className="inline-flex items-center rounded bg-[hsl(var(--muted))] px-2 py-0.5 text-xs font-mono font-medium text-[hsl(var(--foreground))]"
            >
              {kpi}
            </span>
          ))}
        </div>
      )}

      <dd className="text-sm leading-relaxed text-[hsl(var(--muted-foreground))] mb-3">
        {item.description}
      </dd>
      <ul className="space-y-1.5">
        {item.details.map((detail) => (
          <li
            key={detail}
            className="flex gap-2 text-sm leading-relaxed text-[hsl(var(--foreground))]"
          >
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[#FFC300]" />
            {detail}
          </li>
        ))}
      </ul>
    </div>
  );
}
