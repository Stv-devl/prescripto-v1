import { zodResolver } from "@hookform/resolvers/zod";
import {
  Save,
  Pencil,
  X,
  Building2,
  Users,
  Calendar,
  FileText,
  CheckCircle2,
  MapPin,
} from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/utils";
import { updateProjectSchema } from "../types/types";
import type { Project, UpdateProjectInput } from "../types/types";
import { FormField } from "./form/FormField";
import { ReadOnlyField } from "./form/ReadOnlyField";
import { StatusBadge, STATUS_OPTIONS } from "./form/StatusBadge";

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

const inputClasses =
  "w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-sm text-[hsl(var(--foreground))] placeholder:text-muted-foreground/60 placeholder:italic placeholder:text-xs focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]";

interface ProjectInfoFormProps {
  project: Project;
  onSubmit: (data: UpdateProjectInput) => void;
  isPending: boolean;
}

/**
 * Project info panel with read/edit modes, grouped sections, status badges and metadata.
 */
export function ProjectInfoForm({
  project,
  onSubmit,
  isPending,
}: ProjectInfoFormProps): React.JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty, dirtyFields },
  } = useForm<UpdateProjectInput>({
    resolver: zodResolver(updateProjectSchema),
    defaultValues: {
      name: project.name,
      phase: project.phase,
      status: project.status,
      address: project.address,
      client: project.client,
      architect: project.architect,
      architect_address: project.architect_address,
      bureau_thermique: project.bureau_thermique,
      bureau_thermique_address: project.bureau_thermique_address,
      bureau_vrd: project.bureau_vrd,
      bureau_vrd_address: project.bureau_vrd_address,
      bureau_beton: project.bureau_beton,
      bureau_beton_address: project.bureau_beton_address,
      economiste: project.economiste,
      economiste_address: project.economiste_address,
      controleur_technique: project.controleur_technique,
      controleur_technique_address: project.controleur_technique_address,
    },
  });

  useEffect(() => {
    reset({
      name: project.name,
      phase: project.phase,
      status: project.status,
      address: project.address,
      client: project.client,
      architect: project.architect,
      architect_address: project.architect_address,
      bureau_thermique: project.bureau_thermique,
      bureau_thermique_address: project.bureau_thermique_address,
      bureau_vrd: project.bureau_vrd,
      bureau_vrd_address: project.bureau_vrd_address,
      bureau_beton: project.bureau_beton,
      bureau_beton_address: project.bureau_beton_address,
      economiste: project.economiste,
      economiste_address: project.economiste_address,
      controleur_technique: project.controleur_technique,
      controleur_technique_address: project.controleur_technique_address,
    });
  }, [project, reset]);

  const handleCancel = useCallback((): void => {
    reset();
    setIsEditing(false);
  }, [reset]);

  const handleFormSubmit = useCallback(
    (data: UpdateProjectInput): void => {
      onSubmit(data);
      setIsEditing(false);
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
    },
    [onSubmit],
  );

  const dirtyClass = (field: keyof UpdateProjectInput): string =>
    dirtyFields[field] ? "ring-2 ring-[#FFC300]/40" : "";

  // --- Read mode ---
  if (!isEditing) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Success banner */}
        {showSuccess && (
          <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 text-sm text-emerald-400 animate-in fade-in slide-in-from-top-2 duration-300">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            Modifications enregistrees avec succes.
          </div>
        )}

        {/* Header with edit button */}
        <header className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-[hsl(var(--foreground))]">
            Informations du projet
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEditing(true)}
          >
            <Pencil className="mr-1.5 h-3.5 w-3.5" />
            Modifier
          </Button>
        </header>

        {/* Section: Projet */}
        <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-[hsl(var(--foreground))]">
            <Building2 className="h-4 w-4 text-[#FFC300]" />
            Projet
          </div>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Nom
              </dt>
              <dd className="mt-1 text-sm font-medium text-[hsl(var(--foreground))]">
                {project.name}
              </dd>
            </div>
            <div className="flex items-start gap-6">
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Statut
                </dt>
                <dd className="mt-1.5">
                  <StatusBadge status={project.status} />
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Phase
                </dt>
                <dd className="mt-1.5">
                  {project.phase ? (
                    <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-medium text-emerald-400">
                      {project.phase}
                    </span>
                  ) : (
                    <span className="italic text-muted-foreground text-xs">
                      Non renseigne
                    </span>
                  )}
                </dd>
              </div>
            </div>
            <ReadOnlyField label="Client" value={project.client} />
            <div>
              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Adresse
              </dt>
              <dd className="mt-1 text-sm text-[hsl(var(--foreground))]">
                {project.address ? (
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                    {project.address}
                  </span>
                ) : (
                  <span className="italic text-muted-foreground text-xs">
                    Non renseigne
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </article>

        {/* Section: Equipe d'etude */}
        <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-[hsl(var(--foreground))]">
            <Users className="h-4 w-4 text-[#FFC300]" />
            Equipe d'etude
          </div>
          <dl className="space-y-0">
            <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-3">
              <div className="space-y-1">
                <ReadOnlyField label="Architecte" value={project.architect} />
                <ReadOnlyField
                  label="Adresse"
                  value={project.architect_address}
                />
              </div>
              <div className="space-y-1">
                <ReadOnlyField label="Economiste" value={project.economiste} />
                <ReadOnlyField
                  label="Adresse"
                  value={project.economiste_address}
                />
              </div>
              <div className="space-y-1">
                <ReadOnlyField
                  label="Bureau thermique"
                  value={project.bureau_thermique}
                />
                <ReadOnlyField
                  label="Adresse"
                  value={project.bureau_thermique_address}
                />
              </div>
            </div>

            <hr className="my-4 border-[hsl(var(--border))]" />

            <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-3">
              <div className="space-y-1">
                <ReadOnlyField
                  label="Bureau beton"
                  value={project.bureau_beton}
                />
                <ReadOnlyField
                  label="Adresse"
                  value={project.bureau_beton_address}
                />
              </div>
              <div className="space-y-1">
                <ReadOnlyField label="Bureau VRD" value={project.bureau_vrd} />
                <ReadOnlyField
                  label="Adresse"
                  value={project.bureau_vrd_address}
                />
              </div>
              <div className="space-y-1">
                <ReadOnlyField
                  label="Controleur technique"
                  value={project.controleur_technique}
                />
                <ReadOnlyField
                  label="Adresse"
                  value={project.controleur_technique_address}
                />
              </div>
            </div>
          </dl>
        </article>

        {/* Section: Metadonnees */}
        <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-[hsl(var(--foreground))]">
            <Calendar className="h-4 w-4 text-[#FFC300]" />
            Informations
          </div>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Date de creation
              </dt>
              <dd className="mt-1 text-sm text-[hsl(var(--foreground))]">
                {formatDate(project.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Derniere modification
              </dt>
              <dd className="mt-1 text-sm text-[hsl(var(--foreground))]">
                {formatDate(project.updated_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Documents
              </dt>
              <dd className="mt-1 flex items-center gap-1.5 text-sm text-[hsl(var(--foreground))]">
                <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                {project.document_count}
              </dd>
            </div>
          </dl>
        </article>
      </div>
    );
  }

  // --- Edit mode ---
  return (
    <form
      onSubmit={handleSubmit(handleFormSubmit)}
      className="mx-auto max-w-3xl space-y-6"
    >
      {/* Header with save / cancel */}
      <header className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-[hsl(var(--foreground))]">
          Modifier le projet
        </h2>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleCancel}
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            Annuler
          </Button>
          <Button type="submit" size="sm" disabled={!isDirty || isPending}>
            <Save className="mr-1.5 h-3.5 w-3.5" />
            {isPending ? "Enregistrement..." : "Enregistrer"}
          </Button>
        </div>
      </header>

      {/* Section: Projet */}
      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-[hsl(var(--foreground))]">
          <Building2 className="h-4 w-4 text-[#FFC300]" />
          Projet
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <FormField
            id="name"
            label="Nom du projet *"
            error={errors.name?.message}
          >
            <input
              id="name"
              type="text"
              placeholder="Nom du projet"
              {...register("name")}
              className={`${inputClasses} ${dirtyClass("name")}`}
            />
          </FormField>

          <FormField id="status" label="Statut">
            <select
              id="status"
              {...register("status")}
              className={`${inputClasses} ${dirtyClass("status")}`}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </FormField>

          <FormField id="phase" label="Phase">
            <select
              id="phase"
              {...register("phase")}
              className={`${inputClasses} ${dirtyClass("phase")}`}
            >
              {PHASE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </FormField>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField id="client" label="Client">
            <input
              id="client"
              type="text"
              placeholder="Nom du client"
              {...register("client")}
              className={`${inputClasses} ${dirtyClass("client")}`}
            />
          </FormField>

          <FormField id="address" label="Adresse">
            <input
              id="address"
              type="text"
              placeholder="Adresse du chantier"
              {...register("address")}
              className={`${inputClasses} ${dirtyClass("address")}`}
            />
          </FormField>
        </div>
      </article>

      {/* Section: Equipe d'etude */}
      <article className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5 space-y-4">
        <div className="flex items-center gap-2 text-sm font-medium text-[hsl(var(--foreground))]">
          <Users className="h-4 w-4 text-[#FFC300]" />
          Equipe d'etude
        </div>

        <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-3">
          <div className="space-y-2">
            <FormField id="architect" label="Architecte">
              <input
                id="architect"
                type="text"
                placeholder="Nom de l'architecte"
                {...register("architect")}
                className={`${inputClasses} ${dirtyClass("architect")}`}
              />
            </FormField>
            <FormField id="architect_address" label="Adresse">
              <input
                id="architect_address"
                type="text"
                placeholder="Adresse"
                {...register("architect_address")}
                className={`${inputClasses} ${dirtyClass("architect_address")}`}
              />
            </FormField>
          </div>

          <div className="space-y-2">
            <FormField id="economiste" label="Economiste">
              <input
                id="economiste"
                type="text"
                placeholder="Nom de l'economiste"
                {...register("economiste")}
                className={`${inputClasses} ${dirtyClass("economiste")}`}
              />
            </FormField>
            <FormField id="economiste_address" label="Adresse">
              <input
                id="economiste_address"
                type="text"
                placeholder="Adresse"
                {...register("economiste_address")}
                className={`${inputClasses} ${dirtyClass("economiste_address")}`}
              />
            </FormField>
          </div>

          <div className="space-y-2">
            <FormField id="bureau_thermique" label="Bureau thermique">
              <input
                id="bureau_thermique"
                type="text"
                placeholder="Nom du bureau thermique"
                {...register("bureau_thermique")}
                className={`${inputClasses} ${dirtyClass("bureau_thermique")}`}
              />
            </FormField>
            <FormField id="bureau_thermique_address" label="Adresse">
              <input
                id="bureau_thermique_address"
                type="text"
                placeholder="Adresse"
                {...register("bureau_thermique_address")}
                className={`${inputClasses} ${dirtyClass("bureau_thermique_address")}`}
              />
            </FormField>
          </div>
        </div>

        <hr className="border-[hsl(var(--border))]" />

        <div className="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-3">
          <div className="space-y-2">
            <FormField id="bureau_beton" label="Bureau beton">
              <input
                id="bureau_beton"
                type="text"
                placeholder="Nom du bureau beton"
                {...register("bureau_beton")}
                className={`${inputClasses} ${dirtyClass("bureau_beton")}`}
              />
            </FormField>
            <FormField id="bureau_beton_address" label="Adresse">
              <input
                id="bureau_beton_address"
                type="text"
                placeholder="Adresse"
                {...register("bureau_beton_address")}
                className={`${inputClasses} ${dirtyClass("bureau_beton_address")}`}
              />
            </FormField>
          </div>

          <div className="space-y-2">
            <FormField id="bureau_vrd" label="Bureau VRD">
              <input
                id="bureau_vrd"
                type="text"
                placeholder="Nom du bureau VRD"
                {...register("bureau_vrd")}
                className={`${inputClasses} ${dirtyClass("bureau_vrd")}`}
              />
            </FormField>
            <FormField id="bureau_vrd_address" label="Adresse">
              <input
                id="bureau_vrd_address"
                type="text"
                placeholder="Adresse"
                {...register("bureau_vrd_address")}
                className={`${inputClasses} ${dirtyClass("bureau_vrd_address")}`}
              />
            </FormField>
          </div>

          <div className="space-y-2">
            <FormField id="controleur_technique" label="Controleur technique">
              <input
                id="controleur_technique"
                type="text"
                placeholder="Nom du controleur technique"
                {...register("controleur_technique")}
                className={`${inputClasses} ${dirtyClass("controleur_technique")}`}
              />
            </FormField>
            <FormField id="controleur_technique_address" label="Adresse">
              <input
                id="controleur_technique_address"
                type="text"
                placeholder="Adresse"
                {...register("controleur_technique_address")}
                className={`${inputClasses} ${dirtyClass("controleur_technique_address")}`}
              />
            </FormField>
          </div>
        </div>
      </article>
    </form>
  );
}
