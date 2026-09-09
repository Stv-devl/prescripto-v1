const STATUS_OPTIONS = [
  { value: "active", label: "En cours" },
  { value: "termine", label: "Termine" },
  { value: "en_pause", label: "En pause" },
  { value: "annule", label: "Annule" },
] as const;

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  active: { bg: "bg-amber-500/15", text: "text-amber-400" },
  termine: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  en_pause: { bg: "bg-slate-500/15", text: "text-slate-400" },
  annule: { bg: "bg-red-500/15", text: "text-red-400" },
};

export function getStatusLabel(value: string): string {
  return STATUS_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export function StatusBadge({ status }: { status: string }): React.JSX.Element {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.active;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      {getStatusLabel(status)}
    </span>
  );
}

export { STATUS_OPTIONS };
