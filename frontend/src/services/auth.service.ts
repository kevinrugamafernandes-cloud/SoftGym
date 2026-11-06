import { apiClient, clearToken, saveToken } from "@/lib/axios";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from "@/types";

export const authService = {
  login: async (payload: LoginRequest): Promise<TokenResponse> => {
    const { data } = await apiClient.post<TokenResponse>(
      "/auth/login",
      payload
    );
    return data;
  },

  register: async (payload: RegisterRequest): Promise<User> => {
    const { data } = await apiClient.post<User>("/auth/register", payload);
    return data;
  },

  me: async (): Promise<User> => {
    const { data } = await apiClient.get<User>("/auth/me");
    return data;
  },

  /** Cambia la contraseña propia; el servidor cierra las demás sesiones y devuelve un token nuevo. */
  changePassword: async (current_password: string, new_password: string): Promise<void> => {
    const { data } = await apiClient.post<TokenResponse>("/auth/me/password", { current_password, new_password });
    saveToken(data.access_token);
  },

  logout: (): void => {
    clearToken();
  },
};
