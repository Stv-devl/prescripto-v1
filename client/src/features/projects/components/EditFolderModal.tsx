import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import type { Folder } from "../types/types";

const editFolderSchema = z.object({
  lot: z.string().max(100),
  phase: z.string().max(50),
});

const PHASE_OPTIONS = [
  { value: "", label: "Aucune phase" },
  { value: "ESQ", label: "ESQ" },
  { value: "APS", label: "APS" },
  { value: "APD", label: "APD" },
  { value: "PRO", label: "PRO" },
  { value: "DCE", label: "DCE" },
  { value: "EXE", label: "EXE" },
  { value: "DOE", label: "DOE" },
] as const;

interface EditFolderModalProps {
  folder: Folder;
  isPending: boolean;
  onConfirm: (data: { lot: string; phase: string }) => void;
  onClose: () => void;
}

const inputClasses =
  "mt-1 block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#FFC300]";

export function EditFolderModal({
  folder,
  isPending,
  onConfirm,
  onClose,
}: EditFolderModalProps) {
  const lotInputRef = useRef<HTMLInputElement>(null);
  const { dialogRef } = useModalDialog<HTMLFormElement>({
    isOpen: true,
    initialFocusRef: lotInputRef,
  });
  const { register, handleSubmit } = useForm({
    resolver: zodResolver(editFolderSchema),
    defaultValues: { lot: folder.lot, phase: folder.phase },
  });
  const { ref: lotFieldRef, ...lotField } = register("lot");

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
      <form
        ref={dialogRef}
        onSubmit={handleSubmit(onConfirm)}
        className="relative w-full max-w-sm rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label="Modifier le dossier"
        tabIndex={-1}
      >
        <header className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{folder.name}</h2>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm font-medium text-[hsl(var(--foreground))]">
            Lot
            <input
              {...lotField}
              ref={(el) => {
                lotFieldRef(el);
                lotInputRef.current = el;
              }}
              className={inputClasses}
              placeholder="Ex : Gros œuvre"
            />
          </label>

          <label className="block text-sm font-medium text-[hsl(var(--foreground))]">
            Phase
            <select {...register("phase")} className={inputClasses}>
              {PHASE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <footer className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isPending}
          >
            Annuler
          </Button>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </footer>
      </form>
    </div>
  );
}
