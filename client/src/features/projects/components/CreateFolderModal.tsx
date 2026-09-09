import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import {
  createFolderSchema,
  type CreateFolderInput,
} from "../types/types";

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

interface CreateFolderModalProps {
  isPending: boolean;
  onConfirm: (data: CreateFolderInput) => void;
  onClose: () => void;
}

const inputClasses =
  "mt-1 block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#FFC300]";

export function CreateFolderModal({
  isPending,
  onConfirm,
  onClose,
}: CreateFolderModalProps) {
  const nameInputRef = useRef<HTMLInputElement>(null);
  const { dialogRef } = useModalDialog<HTMLFormElement>({
    isOpen: true,
    initialFocusRef: nameInputRef,
  });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateFolderInput>({
    resolver: zodResolver(createFolderSchema),
    defaultValues: { name: "", lot: "", phase: "" },
  });
  const { ref: nameFieldRef, ...nameField } = register("name");

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
        className="relative w-full max-w-md rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6 outline-none"
        role="dialog"
        aria-modal="true"
        aria-label="Créer un dossier"
        tabIndex={-1}
      >
        <header className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Nouveau dossier</h2>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <label className="mb-1 block text-sm font-medium text-[hsl(var(--foreground))]">
          Nom du dossier
          <input
            {...nameField}
            ref={(el) => {
              nameFieldRef(el);
              nameInputRef.current = el;
            }}
            className={inputClasses}
            placeholder="Ex : Plans architecte"
          />
        </label>
        {errors.name && (
          <p className="mt-1 text-xs text-red-400">{errors.name.message}</p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-4">
          <label className="block text-sm font-medium text-[hsl(var(--foreground))]">
            Lot
            <input
              {...register("lot")}
              className={inputClasses}
              placeholder="Ex : Gros œuvre"
            />
          </label>

          <label className="block text-sm font-medium text-[hsl(var(--foreground))]">
            Phase
            <select
              {...register("phase")}
              className={inputClasses}
            >
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
            {isPending ? "Création…" : "Créer"}
          </Button>
        </footer>
      </form>
    </div>
  );
}
