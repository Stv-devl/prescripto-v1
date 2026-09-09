import { apiPost, apiPut } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type { ProfileUpdatePayload, ProfileUpdateResponse } from "../types/types";
import { refineSettingsError } from "./settings.errors";

/**
 * Settings API service — handles profile and password requests.
 */
export function updateProfile(
  data: ProfileUpdatePayload,
): Promise<Result<ProfileUpdateResponse>> {
  return attempt(() => apiPut<ProfileUpdateResponse>("/auth/me", data));
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<Result<{ message: string }>> {
  return attempt(
    () =>
      apiPost<{ message: string }>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      }),
    refineSettingsError,
  );
}
