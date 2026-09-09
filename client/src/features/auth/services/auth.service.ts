import { apiGet, apiPost } from "@/lib/apiClient";
import { attempt, type Result } from "@/lib/result";
import type {
  LoginInput,
  MessageResponse,
  SignupInput,
  TokenResponse,
  User,
} from "../types/types";
import { refineAuthError } from "./auth.errors";

/**
 * Auth API service — handles authentication requests.
 */
export function login(data: LoginInput): Promise<Result<TokenResponse>> {
  return attempt(
    () => apiPost<TokenResponse>("/auth/login", data),
    refineAuthError,
  );
}

export function signup(data: SignupInput): Promise<Result<TokenResponse>> {
  return attempt(
    () => apiPost<TokenResponse>("/auth/signup", data),
    refineAuthError,
  );
}

export function refreshTokens(
  refreshToken: string,
): Promise<Result<TokenResponse>> {
  return attempt(() =>
    apiPost<TokenResponse>("/auth/refresh", { refresh_token: refreshToken }),
  );
}

export function getMe(): Promise<Result<User>> {
  return attempt(() => apiGet<User>("/auth/me"));
}

/** Request a password reset email. */
export function forgotPassword(
  email: string,
): Promise<Result<MessageResponse>> {
  return attempt(() =>
    apiPost<MessageResponse>("/auth/forgot-password", { email }),
  );
}

/** Reset password with a reset token. */
export function resetPassword(
  token: string,
  password: string,
): Promise<Result<MessageResponse>> {
  return attempt(
    () => apiPost<MessageResponse>("/auth/reset-password", { token, password }),
    refineAuthError,
  );
}
