import { Trash2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";

interface DeleteConfirmPopoverProps {
  onConfirm: () => void;
  label: string;
  className?: string;
}

/**
 * Trash icon button that shows a confirmation popover before deleting.
 */
export function DeleteConfirmPopover({
  onConfirm,
  label,
  className = "",
}: DeleteConfirmPopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((prev) => !prev);
        }}
        className="hover:text-red-400"
        aria-label={label}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute right-0 top-6 z-50 w-44 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 shadow-lg">
          <p className="mb-2 text-xs text-[hsl(var(--foreground))]">
            Supprimer cette conversation ?
          </p>
          <div className="flex justify-end gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
              }}
              className="h-7 px-2 text-xs"
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(false);
                onConfirm();
              }}
              className="h-7 px-2 text-xs"
            >
              Supprimer
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
