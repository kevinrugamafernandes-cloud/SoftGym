import { apiClient } from "@/lib/axios";
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

  logout: (): void => {
    localStorage.removeItem("access_token");
  },
};
