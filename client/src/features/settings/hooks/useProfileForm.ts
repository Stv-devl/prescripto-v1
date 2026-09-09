import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toServiceError } from "@/lib/result";
import { userMessageFor } from "@/lib/userMessages";
import { profileUpdateSchema, type ProfileUpdateInput } from "../types/types";
import { useUpdateProfile } from "./hooks";

interface UseProfileFormParams {
  firstName: string | null;
  lastName: string | null;
}

/**
 * Encapsulates profile form logic: validation, mutation, success/error state.
 */
export function useProfileForm({ firstName, lastName }: UseProfileFormParams) {
  const mutation = useUpdateProfile();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileUpdateInput>({
    resolver: zodResolver(profileUpdateSchema),
    defaultValues: {
      firstName: firstName ?? "",
      lastName: lastName ?? "",
    },
  });

  function onSubmit(data: ProfileUpdateInput): void {
    setError(null);
    setSuccess(false);
    mutation.mutate(
      {
        first_name: data.firstName || null,
        last_name: data.lastName || null,
      },
      {
        onSuccess: () => {
          setSuccess(true);
          reset(data);
        },
        onError: (err) => setError(userMessageFor(toServiceError(err).code)),
      },
    );
  }

  return {
    register,
    handleSubmit,
    errors,
    isPending: mutation.isPending,
    isDirty,
    error,
    success,
    onSubmit,
  };
}
