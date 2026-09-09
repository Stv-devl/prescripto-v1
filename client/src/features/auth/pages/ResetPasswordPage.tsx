import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { SuccessModal } from "@/components/feedback/SuccessModal";
import { Button } from "@/components/ui/Button";
import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";
import { useResetPassword } from "../hooks/hooks";
import { resetPasswordSchema, type ResetPasswordInput } from "../types/types";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const mutation = useResetPassword();
  const [error, setError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordInput>({
    resolver: zodResolver(resetPasswordSchema),
  });

  function onSubmit(data: ResetPasswordInput): void {
    if (!token) {
      setError(userMessageFor("invalid_reset_token"));
      return;
    }
    setError(null);
    mutation.mutate(
      { token, data },
      {
        onSuccess: () => setShowSuccess(true),
        onError: (err) => setError(userMessageFor(toServiceError(err).code)),
      },
    );
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
              <KeyRound className="h-5 w-5 text-[#FFC300]" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">Nouveau mot de passe</h2>
              <p className="text-sm text-[#F5F5F5]/50">Choisissez un nouveau mot de passe</p>
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
              htmlFor="password"
              className="block text-sm font-medium text-[#F5F5F5]"
            >
              Nouveau mot de passe
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

          <div className="space-y-2">
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium text-[#F5F5F5]"
            >
              Confirmer le mot de passe
            </label>
            <input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              {...register("confirmPassword")}
              className="block w-full rounded-md border border-[#F5F5F5]/10 bg-[#1C1C1C] px-3 py-2 text-[#F5F5F5] placeholder-[#F5F5F5]/30 focus:border-[#FFC300] focus:outline-none focus:ring-1 focus:ring-[#FFC300]"
              placeholder="••••••••"
            />
            {errors.confirmPassword && (
              <p className="text-sm text-red-400">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <LoadingSpinner size="sm" className="mr-2" />
            ) : null}
            Réinitialiser le mot de passe
          </Button>
        </form>
      </section>

      {showSuccess && (
        <SuccessModal
          title="Mot de passe réinitialisé"
          message="Votre mot de passe a été réinitialisé avec succès."
          actionLabel="Se connecter"
          onAction={() => navigate("/login")}
          onClose={() => navigate("/login")}
        />
      )}
    </main>
  );
}
