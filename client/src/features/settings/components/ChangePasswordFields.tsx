import type { FieldErrors, UseFormRegister } from "react-hook-form";
import type { ChangePasswordInput } from "../types/types";

interface ChangePasswordFieldsProps {
  register: UseFormRegister<ChangePasswordInput>;
  errors: FieldErrors<ChangePasswordInput>;
}

const inputClasses =
  "block w-full rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] px-3 py-2 text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:border-[hsl(var(--primary))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--ring))]";

/**
 * The three password fields of `ChangePasswordModal`, split out to keep the
 * modal under this repo's component size threshold.
 */
export function ChangePasswordFields({
  register,
  errors,
}: ChangePasswordFieldsProps) {
  return (
    <>
      <div className="space-y-2">
        <label
          htmlFor="modal-currentPassword"
          className="block text-sm font-medium text-[hsl(var(--foreground))]"
        >
          Mot de passe actuel
        </label>
        <input
          id="modal-currentPassword"
          type="password"
          autoComplete="current-password"
          {...register("currentPassword")}
          className={inputClasses}
        />
        {errors.currentPassword && (
          <p className="text-sm text-red-400">
            {errors.currentPassword.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="modal-newPassword"
          className="block text-sm font-medium text-[hsl(var(--foreground))]"
        >
          Nouveau mot de passe
        </label>
        <input
          id="modal-newPassword"
          type="password"
          autoComplete="new-password"
          {...register("newPassword")}
          className={inputClasses}
        />
        <p className="text-xs text-[hsl(var(--muted-foreground))]">
          Min. 8 caractères, 1 majuscule, 1 chiffre et 1 caractère spécial
        </p>
        {errors.newPassword && (
          <p className="text-sm text-red-400">{errors.newPassword.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <label
          htmlFor="modal-confirmNewPassword"
          className="block text-sm font-medium text-[hsl(var(--foreground))]"
        >
          Confirmer le nouveau mot de passe
        </label>
        <input
          id="modal-confirmNewPassword"
          type="password"
          autoComplete="new-password"
          {...register("confirmNewPassword")}
          className={inputClasses}
        />
        {errors.confirmNewPassword && (
          <p className="text-sm text-red-400">
            {errors.confirmNewPassword.message}
          </p>
        )}
      </div>
    </>
  );
}
