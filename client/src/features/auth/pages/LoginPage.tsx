import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { Button } from "@/components/ui/Button";
import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";
import { useLogin } from "../hooks/hooks";
import { loginSchema, type LoginInput } from "../types/types";

export function LoginPage() {
  const navigate = useNavigate();
  const loginMutation = useLogin();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
  });

  function onSubmit(data: LoginInput): void {
    setError(null);
    loginMutation.mutate(data, {
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
              <LogIn className="h-5 w-5 text-[#FFC300]" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">Connexion</h2>
              <p className="text-sm text-[#F5F5F5]/50">Connectez-vous à votre espace</p>
            </div>
          </div>

          {error && (
            <p
              className="rounded-md bg-red-500/10 p-3 text-sm text-red-400"
              role="alert"
            >
              {error}
            </p>
          )}

          <div className="space-y-2">
            <label
              htmlFor="email"
              className="block text-sm font-medium text-[#F5F5F5]"
            >
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
            <label
              htmlFor="password"
              className="block text-sm font-medium text-[#F5F5F5]"
            >
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              {...register("password")}
              className="block w-full rounded-md border border-[#F5F5F5]/10 bg-[#1C1C1C] px-3 py-2 text-[#F5F5F5] placeholder-[#F5F5F5]/30 focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              placeholder="••••••••"
            />
            {errors.password && (
              <p className="text-sm text-red-400">{errors.password.message}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? (
              <LoadingSpinner size="sm" className="mr-2" />
            ) : null}
            Se connecter
          </Button>

          <p className="text-center text-sm">
            <Link
              to="/forgot-password"
              className="text-[#F5F5F5]/60 hover:text-[#F5F5F5] hover:underline"
            >
              Mot de passe oublié ?
            </Link>
          </p>

          <p className="text-center text-sm text-[#F5F5F5]/60">
            Pas encore de compte ?{" "}
            <Link to="/signup" className="text-[#FFC300] hover:underline">
              Créer un compte
            </Link>
          </p>
        </form>
      </section>
    </main>
  );
}
