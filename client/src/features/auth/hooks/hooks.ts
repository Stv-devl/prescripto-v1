import { useMutation, useQueryClient } from "@tanstack/react-query";
import { unwrap } from "@/lib/result";
import { useAuthStore } from "@/lib/store/authStore";
import * as authService from "../services/auth.service";
import type {
  ForgotPasswordInput,
  LoginInput,
  ResetPasswordInput,
  SignupInput,
} from "../types/types";

/**
 * Login mutation — authenticates and stores tokens.
 */
export function useLogin() {
  const queryClient = useQueryClient();
  const openSession = useAuthStore((s) => s.openSession);

  return useMutation({
    mutationFn: async (data: LoginInput) => unwrap(await authService.login(data)),
    onSuccess: (res) => {
      queryClient.clear();
      openSession(res.access_token, res.refresh_token);
    },
  });
}

/**
 * Signup mutation — registers and stores tokens.
 */
export function useSignup() {
  const queryClient = useQueryClient();
  const openSession = useAuthStore((s) => s.openSession);

  return useMutation({
    mutationFn: async (data: SignupInput) =>
      unwrap(await authService.signup(data)),
    onSuccess: (res) => {
      queryClient.clear();
      openSession(res.access_token, res.refresh_token);
    },
  });
}

/**
 * Forgot password mutation — sends reset email.
 */
export function useForgotPassword() {
  return useMutation({
    mutationFn: async (data: ForgotPasswordInput) =>
      unwrap(await authService.forgotPassword(data.email)),
  });
}

/**
 * Reset password mutation — resets via token.
 */
export function useResetPassword() {
  return useMutation({
    mutationFn: async ({
      token,
      data,
    }: {
      token: string;
      data: ResetPasswordInput;
    }) => unwrap(await authService.resetPassword(token, data.password)),
  });
}
