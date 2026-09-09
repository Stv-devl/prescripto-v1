import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";

interface DeleteDocumentModalProps {
  filename: string;
  isPending: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function DeleteDocumentModal({
  filename,
  isPending,
  onConfirm,
  onClose,
}: DeleteDocumentModalProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const { dialogRef } = useModalDialog<HTMLDivElement>({
    isOpen: true,
    initialFocusRef: cancelRef,
  });

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        className="absolute inset-0 bg-black/60"
        role="presentation"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="relative w-full max-w-md rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label="Confirmer la suppression du document"
        tabIndex={-1}
      >
        <header className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-red-400">
            Supprimer le document
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <p className="mb-6 text-sm text-[hsl(var(--muted-foreground))]">
          Vous êtes sur le point de supprimer{" "}
          <strong className="text-[hsl(var(--foreground))]">
            « {filename} »
          </strong>
          . Cette action est irréversible.
        </p>

        <footer className="flex justify-end gap-2">
          <Button
            ref={cancelRef}
            variant="outline"
            onClick={onClose}
            disabled={isPending}
          >
            Annuler
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? "Suppression…" : "Supprimer"}
          </Button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
