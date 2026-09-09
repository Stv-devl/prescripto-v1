import { CheckCircle, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";

interface SuccessModalProps {
  title: string;
  message: string;
  actionLabel: string;
  onAction: () => void;
  onClose: () => void;
}

/**
 * Reusable success confirmation modal.
 */
export function SuccessModal({
  title,
  message,
  actionLabel,
  onAction,
  onClose,
}: SuccessModalProps) {
  const actionRef = useRef<HTMLButtonElement>(null);
  const { dialogRef } = useModalDialog<HTMLDivElement>({
    isOpen: true,
    initialFocusRef: actionRef,
  });

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60"
        role="presentation"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="relative w-full max-w-md rounded-lg border border-[#F5F5F5]/10 bg-[#2B2B2B] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <header className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-400" />
            <h2 className="text-lg font-semibold text-[#F5F5F5]">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <p className="mb-6 text-sm text-[#F5F5F5]/80">{message}</p>

        <footer className="flex justify-end">
          <Button ref={actionRef} onClick={onAction}>
            {actionLabel}
          </Button>
        </footer>
      </div>
    </div>
  );
}
