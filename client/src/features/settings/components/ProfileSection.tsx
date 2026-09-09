import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import { useProfileForm } from "../hooks/hooks";

interface ProfileSectionProps {
  firstName: string | null;
  lastName: string | null;
  email: string;
}

export function ProfileSection({
  firstName,
  lastName,
  email,
}: ProfileSectionProps) {
  const {
    register,
    handleSubmit,
    errors,
    isPending,
    isDirty,
    error,
    success,
    onSubmit,
  } = useProfileForm({ firstName, lastName });

  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold text-[hsl(var(--foreground))]">
        Profil
      </h2>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-5 rounded-lg bg-[hsl(var(--secondary))] p-6"
      >
        {error && (
          <p
            className="rounded-md bg-red-500/10 p-3 text-sm text-red-400"
            role="alert"
          >
            {error}
          </p>
        )}

        {success && (
          <p className="rounded-md bg-green-500/10 p-3 text-sm text-green-400">
            Profil mis à jour avec succès.
          </p>
        )}

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <label
              htmlFor="firstName"
              className="block text-sm font-medium text-[hsl(var(--foreground))]"
            >
              Prénom
            </label>
            <input
              id="firstName"
              type="text"
              autoComplete="given-name"
              {...register("firstName")}
              className="block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-[hsl(var(--primary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--ring))]"
              placeholder="Votre prénom"
            />
            {errors.firstName && (
              <p className="text-sm text-red-400">{errors.firstName.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <label
              htmlFor="lastName"
              className="block text-sm font-medium text-[hsl(var(--foreground))]"
            >
              Nom
            </label>
            <input
              id="lastName"
              type="text"
              autoComplete="family-name"
              {...register("lastName")}
              className="block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-[hsl(var(--primary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--ring))]"
              placeholder="Votre nom"
            />
            {errors.lastName && (
              <p className="text-sm text-red-400">{errors.lastName.message}</p>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="email"
            className="block text-sm font-medium text-[hsl(var(--foreground))]"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            readOnly
            className="block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-[hsl(var(--muted-foreground))] cursor-not-allowed"
          />
          <p className="text-xs text-[hsl(var(--muted-foreground))]">
            L'adresse email ne peut pas être modifiée.
          </p>
        </div>

        <Button type="submit" disabled={isPending || !isDirty}>
          {isPending ? <LoadingSpinner size="sm" className="mr-2" /> : null}
          Enregistrer
        </Button>
      </form>
    </section>
  );
}
