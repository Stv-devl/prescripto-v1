export function ReadOnlyField({
  label,
  value,
}: {
  label: string;
  value: string;
}): React.JSX.Element {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-[hsl(var(--foreground))]">
        {value || (
          <span className="italic text-muted-foreground text-xs">
            Non renseigne
          </span>
        )}
      </dd>
    </div>
  );
}
