import { useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import { beginSessionScope } from "@/lib/store/sessionReset";
import type { User } from "@/types/user";
import * as settingsService from "../services/settings.service";
import type { ProfileUpdatePayload } from "../types/types";

/**
 * Update profile mutation — optimistic update on ["auth", "me"], rollback on error.
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ProfileUpdatePayload) =>
      unwrap(await settingsService.updateProfile(data)),
    onMutate: async (newData) => {
      const inSession = beginSessionScope();
      await queryClient.cancelQueries({ queryKey: ["auth", "me"] });
      const previous = queryClient.getQueryData<User>(["auth", "me"]);

      if (previous) {
        queryClient.setQueryData<User>(["auth", "me"], {
          ...previous,
          first_name: newData.first_name,
          last_name: newData.last_name,
        });
      }

      return { previous, inSession };
    },
    onError: (_err, _vars, context) => {
      const previous = context?.previous;
      if (!previous) return;
      context.inSession(() => {
        queryClient.setQueryData(["auth", "me"], previous);
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export { useProfileForm } from "./useProfileForm";
export { useChangePassword } from "./useChangePassword";
