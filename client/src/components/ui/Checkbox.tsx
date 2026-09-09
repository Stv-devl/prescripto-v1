import { useEffect, useRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface CheckboxProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type"
> {
  indeterminate?: boolean;
}

/**
 * Styled checkbox with gray background and accent-[#FFC300].
 * Uses appearance-none for full style control.
 */
export function Checkbox({
  className,
  indeterminate = false,
  ...props
}: CheckboxProps): React.ReactElement {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      className={cn(
        "h-4 w-4 cursor-pointer appearance-none rounded border border-[hsl(var(--border))] bg-neutral-300 transition-colors",
        "checked:bg-[#FFC300] checked:border-[#FFC300]",
        "indeterminate:bg-[#FFC300] indeterminate:border-[#FFC300]",
        "focus:ring-1 focus:ring-[#FFC300] focus:ring-offset-0 focus:outline-none",
        "relative after:absolute after:inset-0 after:hidden after:content-['']",
        "checked:after:block checked:after:border-[hsl(var(--background))] checked:after:border-b-2 checked:after:border-r-2 checked:after:w-[5px] checked:after:h-[9px] checked:after:left-[4px] checked:after:top-[0.5px] checked:after:rotate-45",
        "indeterminate:after:block indeterminate:after:bg-[hsl(var(--background))] indeterminate:after:w-[8px] indeterminate:after:h-[2px] indeterminate:after:left-[3px] indeterminate:after:top-[6px] indeterminate:after:rounded-full",
        className,
      )}
      {...props}
    />
  );
}
