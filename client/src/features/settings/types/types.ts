import { z } from "zod";
import { passwordRules } from "@/lib/validation/passwordSchema";

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Mot de passe actuel requis"),
    newPassword: passwordRules,
    confirmNewPassword: z.string().min(1, "Veuillez confirmer le mot de passe"),
  })
  .refine((data) => data.newPassword === data.confirmNewPassword, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirmNewPassword"],
  });

export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;

export const profileUpdateSchema = z.object({
  firstName: z
    .string()
    .max(100, "100 caractères maximum")
    .optional()
    .or(z.literal("")),
  lastName: z
    .string()
    .max(100, "100 caractères maximum")
    .optional()
    .or(z.literal("")),
});

export type ProfileUpdateInput = z.infer<typeof profileUpdateSchema>;

export interface ProfileUpdatePayload {
  first_name: string | null;
  last_name: string | null;
}

export interface ProfileUpdateResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  tenant_name: string | null;
  tenant_plan: string | null;
}
