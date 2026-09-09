import { useMutation } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import * as settingsService from "../services/settings.service";

/**
 * Change password mutation — wraps settingsService.changePassword.
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: async ({
      currentPassword,
      newPassword,
    }: {
      currentPassword: string;
      newPassword: string;
    }) => unwrap(await settingsService.changePassword(currentPassword, newPassword)),
  });
}
