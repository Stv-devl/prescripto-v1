export function FormField({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <fieldset>
      <label
        htmlFor={id}
        className="mb-1 block text-sm font-medium text-[hsl(var(--foreground))]"
      >
        {label}
      </label>
      {children}
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </fieldset>
  );
}
