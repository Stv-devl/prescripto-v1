import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import { useCreateProject } from "../hooks/hooks";
import { createProjectSchema, type CreateProjectInput } from "../types/types";

interface CreateProjectModalProps {
  onClose: () => void;
}

export function CreateProjectModal({ onClose }: CreateProjectModalProps) {
  const createProject = useCreateProject();
  const { dialogRef } = useModalDialog<HTMLDivElement>({ isOpen: true });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateProjectInput>({
    resolver: zodResolver(createProjectSchema),
    defaultValues: { name: "", phase: "" },
  });

  function onSubmit(data: CreateProjectInput): void {
    createProject.mutate(data, { onSuccess: onClose });
  }

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 outline-none"
      role="dialog"
      aria-modal="true"
      aria-label="Créer un projet"
      tabIndex={-1}
    >
      <div className="w-full max-w-md rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] p-6">
        <header className="mb-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Créer un projet</h2>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Renseignez les informations de votre nouveau projet.
          </p>
        </header>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1">
            <label htmlFor="name" className="text-sm font-medium">
              Nom du projet
            </label>
            <input
              id="name"
              type="text"
              className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]"
              placeholder="Ex : Résidence Les Lilas"
              {...register("name")}
            />
            {errors.name && (
              <p className="text-xs text-red-400">{errors.name.message}</p>
            )}
          </fieldset>

          <fieldset className="flex flex-col gap-1">
            <label htmlFor="phase" className="text-sm font-medium">
              Phase (optionnel)
            </label>
            <input
              id="phase"
              type="text"
              className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]"
              placeholder="Ex : APD, DCE, PRO…"
              {...register("phase")}
            />
          </fieldset>

          <footer className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={createProject.isPending}>
              {createProject.isPending ? "Création…" : "Créer"}
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}
