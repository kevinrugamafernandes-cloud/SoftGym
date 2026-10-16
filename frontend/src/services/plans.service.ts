import { apiClient } from "@/lib/axios";
import type { Plan, PlanCreatePayload, PlanUpdatePayload } from "@/types";

export const plansService = {
  list: async (activeOnly = false, signal?: AbortSignal): Promise<Plan[]> => {
    const { data } = await apiClient.get<Plan[]>("/plans", {
      params: activeOnly ? { active_only: true } : undefined,
      signal,
    });
    return data;
  },

  get: async (id: string, signal?: AbortSignal): Promise<Plan> => {
    const { data } = await apiClient.get<Plan>(`/plans/${id}`, { signal });
    return data;
  },

  create: async (payload: PlanCreatePayload): Promise<Plan> => {
    const { data } = await apiClient.post<Plan>("/plans", payload);
    return data;
  },

  update: async (id: string, payload: PlanUpdatePayload): Promise<Plan> => {
    const { data } = await apiClient.patch<Plan>(`/plans/${id}`, payload);
    return data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/plans/${id}`);
  },
};
