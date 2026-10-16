import { apiClient } from "@/lib/axios";
import type {
  CedulaLookupResult,
  Member,
  MemberCreatePayload,
  MemberFilters,
  MemberListResponse,
  MemberUpdatePayload,
} from "@/types";

export const membersService = {
  list: async (filters: MemberFilters, signal?: AbortSignal): Promise<MemberListResponse> => {
    const search = filters.search.trim();
    const { data } = await apiClient.get<MemberListResponse>("/members", {
      params: {
        ...(search ? { search } : {}),
        ...(filters.status ? { status: filters.status } : {}),
        page: filters.page,
        size: filters.size,
      },
      signal,
    });
    return data;
  },

  get: async (id: string, signal?: AbortSignal): Promise<Member> => {
    const { data } = await apiClient.get<Member>(`/members/${id}`, { signal });
    return data;
  },

  create: async (payload: MemberCreatePayload): Promise<Member> => {
    const { data } = await apiClient.post<Member>("/members", payload);
    return data;
  },

  update: async (id: string, payload: MemberUpdatePayload): Promise<Member> => {
    const { data } = await apiClient.patch<Member>(`/members/${id}`, payload);
    return data;
  },

  /** Baja lógica (solo administradores): conserva el historial. */
  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/members/${id}`);
  },

  /** Restaura a un socio dado de baja (solo administradores). */
  restore: async (id: string): Promise<Member> => {
    const { data } = await apiClient.post<Member>(`/members/${id}/restore`);
    return data;
  },

  /**
   * Fácil Inscripción. El backend puede tardar (3 intentos de hasta 5 s con Hacienda),
   * así que se acota a 10 s: pasado ese tiempo la UI cae al ingreso manual.
   */
  lookupCedula: async (identification: string, signal?: AbortSignal): Promise<CedulaLookupResult> => {
    const { data } = await apiClient.get<CedulaLookupResult>(
      `/members/cedula-lookup/${encodeURIComponent(identification)}`,
      { signal, timeout: 10_000 }
    );
    return data;
  },
};
