import { cn } from "@/lib/utils";

const MARKS = [1, 2, 3, 4, 5];

interface RatingProps {
  /** Marks to fill, clamped to 0..5 for display. */
  value: number;
}

/**
 * A rating shown as five marks, filled up to `value`.
 *
 * The group carries `role="img"` so its label reaches the accessibility tree:
 * an `aria-label` on a generic element is not part of the accessible name.
 *
 * Bars, not discs: the carousel paginates with small filled circles, and two
 * meanings sharing one shape read as one. An empty mark is a solid muted bar,
 * not a hairline outline, so it clears the 3:1 a graphical object needs.
 */
export function Rating({ value }: RatingProps): React.JSX.Element {
  const filled = Math.min(Math.max(Math.round(value), 0), MARKS.length);

  return (
    <div
      role="img"
      aria-label={`Note : ${filled} sur ${MARKS.length}`}
      className="flex items-center gap-1"
    >
      {MARKS.map((mark) => (
        <span
          key={mark}
          aria-hidden="true"
          data-filled={mark <= filled}
          className={cn(
            "h-3 w-1.5 rounded-[2px]",
            mark <= filled ? "bg-[#FFC300]" : "bg-[#F5F5F5]/50",
          )}
        />
      ))}
    </div>
  );
}
