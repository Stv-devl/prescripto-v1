import { Thermometer, Wind, Activity, TriangleAlert } from "lucide-react";
import type { ContrainteItem } from "../types/types";

const CONTRAINTE_ICONS: Record<string, React.ReactNode> = {
  "Réglementation thermique": <Thermometer className="h-3.5 w-3.5" />,
  "Vent & Pluie": <Wind className="h-3.5 w-3.5" />,
  Sismique: <Activity className="h-3.5 w-3.5" />,
  "Contraintes constructives": <TriangleAlert className="h-3.5 w-3.5" />,
};

interface ProjectSummaryTabContrainteEntryProps {
  item: ContrainteItem;
}

/** One regulatory-constraint entry of the project summary report. */
export function ProjectSummaryTabContrainteEntry({
  item,
}: ProjectSummaryTabContrainteEntryProps): React.ReactElement {
  const icon = CONTRAINTE_ICONS[item.label] ?? (
    <TriangleAlert className="h-3.5 w-3.5" />
  );

  return (
    <div className="py-4">
      <div className="flex items-center gap-2.5 mb-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-amber-500/80">
          {icon}
        </span>
        <dt className="text-[13px] font-semibold text-[hsl(var(--foreground))] tracking-tight">
          {item.label}
        </dt>
      </div>
      {item.kpis.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {item.kpis.map((kpi) => (
            <span
              key={kpi}
              className="inline-flex items-center rounded bg-amber-500/10 px-2 py-0.5 text-xs font-mono font-medium text-amber-500"
            >
              {kpi}
            </span>
          ))}
        </div>
      )}
      <dd>
        <ul className="space-y-1">
          {item.details.map((detail) => (
            <li
              key={detail}
              className="flex gap-2 text-sm leading-relaxed text-[hsl(var(--foreground))]"
            >
              <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-amber-500/60" />
              {detail}
            </li>
          ))}
        </ul>
      </dd>
    </div>
  );
}
