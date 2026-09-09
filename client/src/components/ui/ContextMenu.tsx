import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef, useCallback, type ReactElement } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

export interface ContextMenuItem {
  label: string;
  icon?: ReactElement;
  onClick: () => void;
  variant?: "default" | "destructive";
}

interface ContextMenuProps {
  isOpen: boolean;
  position: { x: number; y: number };
  items: ContextMenuItem[];
  onClose: () => void;
}

/**
 * Portal-based context menu with viewport-aware positioning and Framer Motion animation.
 */
export function ContextMenu({
  isOpen,
  position,
  items,
  onClose,
}: ContextMenuProps): ReactElement | null {
  const menuRef = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(
    (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    },
    [onClose],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", onClose, true);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", onClose, true);
    };
  }, [isOpen, handleClickOutside, handleKeyDown, onClose]);

  /** Keeps the menu on screen, flipping it when it would overflow. */
  const getAdjustedPosition = (): { x: number; y: number } => {
    const menuWidth = 192;
    const menuHeight = items.length * 36 + 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let x = position.x;
    let y = position.y;

    if (x + menuWidth > vw) x = vw - menuWidth - 8;
    if (y + menuHeight > vh) y = vh - menuHeight - 8;
    if (x < 8) x = 8;
    if (y < 8) y = 8;

    return { x, y };
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          ref={menuRef}
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.92 }}
          transition={{ duration: 0.12 }}
          className="fixed z-50 min-w-[192px] rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] py-1 shadow-xl"
          style={{
            left: getAdjustedPosition().x,
            top: getAdjustedPosition().y,
          }}
          role="menu"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={cn(
                "flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors",
                item.variant === "destructive"
                  ? "text-red-400 hover:bg-red-500/10"
                  : "text-[hsl(var(--foreground))] hover:bg-[hsl(var(--muted))]",
              )}
              onClick={(e) => {
                e.stopPropagation();
                item.onClick();
                onClose();
              }}
            >
              {item.icon && (
                <span className="h-4 w-4 shrink-0">{item.icon}</span>
              )}
              {item.label}
            </button>
          ))}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
