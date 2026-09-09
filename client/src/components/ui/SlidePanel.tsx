import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import {
  useEffect,
  useCallback,
  type ReactNode,
  type ReactElement,
} from "react";
import { createPortal } from "react-dom";
import { useModalDialog, type ReadOnlyRef } from "@/hooks/useModalDialog";
import { Button } from "./Button";

interface SlidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: string;
  /** Receives focus on close when the element that opened the panel is gone. */
  fallbackFocusRef?: ReadOnlyRef;
}

/**
 * Right-side slide-in modal dialog, animated, rendered in a portal on `<body>`.
 *
 * The portal is load-bearing, not cosmetic: it puts the panel outside `#root`,
 * which the hook then marks `inert` while the panel is open. Focus is trapped
 * inside and handed back on close.
 */
export function SlidePanel({
  isOpen,
  onClose,
  title,
  children,
  width = "w-[420px]",
  fallbackFocusRef,
}: SlidePanelProps): ReactElement {
  const { dialogRef, titleId } = useModalDialog({ isOpen, fallbackFocusRef });

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleKeyDown]);

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/40"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Panel */}
          <motion.aside
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className={`fixed right-0 top-0 z-50 flex h-full ${width} flex-col border-l border-[hsl(var(--border))] bg-[hsl(var(--background))] outline-none`}
          >
            <header className="flex items-center justify-between border-b border-[hsl(var(--border))] px-5 py-4">
              <h2
                id={titleId}
                className="text-sm font-semibold text-[hsl(var(--foreground))]"
              >
                {title}
              </h2>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={onClose}
                aria-label="Fermer"
              >
                <X className="h-4 w-4" />
              </Button>
            </header>
            <div className="flex-1 overflow-y-auto p-5">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
