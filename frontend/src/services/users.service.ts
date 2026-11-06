import { apiClient } from "@/lib/axios";
import type { StaffUser, StaffUserCreate, StaffUserUpdate } from "@/types";

/** Cuentas del personal del gimnasio (solo administrador). */
export const usersService = {
  list: async (signal?: AbortSignal): Promise<StaffUser[]> =>
    (await apiClient.get<{ items: StaffUser[] }>("/users", { signal })).data.items,
  create: async (payload: StaffUserCreate): Promise<StaffUser> =>
    (await apiClient.post<StaffUser>("/auth/register", payload)).data,
  update: async (id: string, payload: StaffUserUpdate): Promise<StaffUser> =>
    (await apiClient.patch<StaffUser>(`/users/${id}`, payload)).data,
  resetPassword: async (id: string, new_password: string): Promise<StaffUser> =>
    (await apiClient.post<StaffUser>(`/users/${id}/password`, { new_password })).data,
};
