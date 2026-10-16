import { apiClient } from "@/lib/axios";
import type { CashSession, CashSessionFilters, CashSessionList } from "@/types";

export const cashSessionsService = {
  /** Caja abierta del usuario, o null. */
  current: async (signal?: AbortSignal): Promise<CashSession | null> => {
    const { data } = await apiClient.get<{ session: CashSession | null }>("/cash-sessions/current", { signal });
    return data.session;
  },

  open: async (payload: { opening_float: string; notes?: string | null }): Promise<CashSession> => {
    const { data } = await apiClient.post<CashSession>("/cash-sessions/open", payload);
    return data;
  },

  close: async (id: string, payload: { counted_cash: string; notes?: string | null }): Promise<CashSession> => {
    const { data } = await apiClient.post<CashSession>(`/cash-sessions/${id}/close`, payload);
    return data;
  },

  get: async (id: string, signal?: AbortSignal): Promise<CashSession> => {
    const { data } = await apiClient.get<CashSession>(`/cash-sessions/${id}`, { signal });
    return data;
  },

  list: async (f: CashSessionFilters, signal?: AbortSignal): Promise<CashSessionList> => {
    const { data } = await apiClient.get<CashSessionList>("/cash-sessions", {
      params: {
        ...(f.date_from ? { date_from: f.date_from } : {}),
        ...(f.date_to ? { date_to: f.date_to } : {}),
        ...(f.status ? { status: f.status } : {}),
        page: f.page,
        size: f.size,
      },
      signal,
    });
    return data;
  },
};
