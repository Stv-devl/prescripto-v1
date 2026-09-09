import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { LoadingSpinner } from "@/components/feedback/LoadingSpinner";
import { SuccessModal } from "@/components/feedback/SuccessModal";
import { Button } from "@/components/ui/Button";
import { useModalDialog } from "@/hooks/useModalDialog";
import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";
import { useChangePassword } from "../hooks/hooks";
import { changePasswordSchema, type ChangePasswordInput } from "../types/types";
import { ChangePasswordFields } from "./ChangePasswordFields";

interface ChangePasswordModalProps {
  onClose: () => void;
}

export function ChangePasswordModal({ onClose }: ChangePasswordModalProps) {
  const mutation = useChangePassword();
  const [error, setError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const { dialogRef } = useModalDialog<HTMLDivElement>({ isOpen: !showSuccess });

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ChangePasswordInput>({
    resolver: zodResolver(changePasswordSchema),
  });

  async function handleFormSubmit(data: ChangePasswordInput): Promise<void> {
    setError(null);
    try {
      await mutation.mutateAsync({
        currentPassword: data.currentPassword,
        newPassword: data.newPassword,
      });
      setShowSuccess(true);
      reset();
    } catch (err) {
      setError(userMessageFor(toServiceError(err).code));
    }
  }

  if (showSuccess) {
    return (
      <SuccessModal
        title="Mot de passe modifié"
        message="Votre mot de passe a été modifié avec succès."
        actionLabel="Fermer"
        onAction={onClose}
        onClose={onClose}
      />
    );
  }

  return (
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
        aria-label="Changer le mot de passe"
        tabIndex={-1}
      >
        <header className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[hsl(var(--foreground))]">
            Changer le mot de passe
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </header>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-5">
          {error && (
            <p
              className="rounded-md bg-red-500/10 p-3 text-sm text-red-400"
              role="alert"
            >
              {error}
            </p>
          )}

          <ChangePasswordFields register={register} errors={errors} />

          <footer className="flex justify-end gap-3 pt-2">
            <Button variant="outline" type="button" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <LoadingSpinner size="sm" className="mr-2" />
              ) : null}
              Modifier
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}
