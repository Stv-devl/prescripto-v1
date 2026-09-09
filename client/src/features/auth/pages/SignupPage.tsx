import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";
import { useSignup } from "../hooks/hooks";
import { signupSchema, type SignupInput } from "../types/types";

export function SignupPage() {
  const navigate = useNavigate();
  const signupMutation = useSignup();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupInput>({
    resolver: zodResolver(signupSchema),
  });

  function onSubmit(data: SignupInput): void {
    setError(null);
    signupMutation.mutate(data, {
      onSuccess: () => navigate("/projects"),
      onError: (err) => setError(userMessageFor(toServiceError(err).code)),
    });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#1C1C1C] px-4">
      <section className="w-full max-w-md space-y-8">
        <header className="text-center">
          <h1 className="flex items-center justify-center gap-3 text-3xl font-bold text-[#FFC300]">
            <img src="/prescripto-logo.webp" alt="" width={36} height={36} className="h-9 w-9" />
            Prescripto
          </h1>
        </header>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-5 rounded-lg bg-[#2B2B2B] p-8"
        >
          <div className="flex items-center gap-3 border-b border-[#F5F5F5]/10 pb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FFC300]/10">
              <UserPlus className="h-5 w-5 text-[#FFC300]" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">Créer un compte</h2>
              <p className="text-sm text-[#F5F5F5]/50">Créez votre espace cabinet</p>
            </div>
          </div>

          {error && (
            <p className="rounded-md bg-red-500/10 p-3 text-sm text-red-400" role="alert">
              {error}
            </p>
          )}

          <div className="space-y-2">
            <label htmlFor="name" className="block text-sm font-medium text-[#F5F5F5]">
              Nom du cabinet
            </label>
            <input
              id="name"
              type="text"
              autoComplete="organization"
              {...register("name")}
              className="block w-full rounded-md border border-[#F5F5F5]/10 bg-[#1C1C1C] px-3 py-2 text-[#F5F5F5] placeholder-[#F5F5F5]/30 focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              placeholder="Mon Cabinet"
            />
            {errors.name && (
              <p className="text-sm text-red-400">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="email" className="block text-sm font-medium text-[#F5F5F5]">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
              className="block w-full rounded-md border border-[#F5F5F5]/10 bg-[#1C1C1C] px-3 py-2 text-[#F5F5F5] placeholder-[#F5F5F5]/30 focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              placeholder="vous@cabinet.fr"
            />
            {errors.email && (
              <p className="text-sm text-red-400">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="block text-sm font-medium text-[#F5F5F5]">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
              className="block w-full rounded-md border border-[#F5F5F5]/10 bg-[#1C1C1C] px-3 py-2 text-[#F5F5F5] placeholder-[#F5F5F5]/30 focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              placeholder="••••••••"
            />
            <p className="text-xs text-[#F5F5F5]/40">
              Min. 8 caractères, 1 majuscule, 1 chiffre et 1 caractère spécial
            </p>
            {errors.password && (
              <p className="text-sm text-red-400">{errors.password.message}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={signupMutation.isPending}
          >
            {signupMutation.isPending ? (
              <LoadingSpinner size="sm" className="mr-2" />
            ) : null}
            Créer mon compte
          </Button>

          <p className="text-center text-sm text-[#F5F5F5]/60">
            Déjà un compte ?{" "}
            <Link to="/login" className="text-[#FFC300] hover:underline">
              Se connecter
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
