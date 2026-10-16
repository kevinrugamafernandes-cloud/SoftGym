import { apiClient } from "@/lib/axios";
import type {
  Measurement,
  MeasurementCreatePayload,
  MeasurementHistory,
  MeasurementUpdatePayload,
} from "@/types";

const base = (memberId: string) => `/members/${memberId}/measurements`;

export const measurementsService = {
  list: async (memberId: string, limit: number, signal?: AbortSignal): Promise<MeasurementHistory> => {
    const { data } = await apiClient.get<MeasurementHistory>(base(memberId), {
      params: { limit },
      signal,
    });
    return data;
  },

  /** El IMC y su clasificación los calcula el servidor y vuelven en la respuesta. */
  create: async (memberId: string, payload: MeasurementCreatePayload): Promise<Measurement> => {
    const { data } = await apiClient.post<Measurement>(base(memberId), payload);
    return data;
  },

  update: async (
    memberId: string,
    measurementId: string,
    payload: MeasurementUpdatePayload
  ): Promise<Measurement> => {
    const { data } = await apiClient.patch<Measurement>(`${base(memberId)}/${measurementId}`, payload);
    return data;
  },

  remove: async (memberId: string, measurementId: string): Promise<void> => {
    await apiClient.delete(`${base(memberId)}/${measurementId}`);
  },
};
