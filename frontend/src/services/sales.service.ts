import { apiClient } from "@/lib/axios";
import { unwrapBlobError } from "@/lib/pdf";
import type { Sale, SaleCreatePayload, SaleFilters, SaleList, WhatsAppLink } from "@/types";

export const salesService = {
  create: async (payload: SaleCreatePayload): Promise<Sale> => {
    const { data } = await apiClient.post<Sale>("/sales", payload);
    return data;
  },

  list: async (f: SaleFilters, signal?: AbortSignal): Promise<SaleList> => {
    const { data } = await apiClient.get<SaleList>("/sales", {
      params: {
        ...(f.date_from ? { date_from: f.date_from } : {}),
        ...(f.date_to ? { date_to: f.date_to } : {}),
        ...(f.method ? { method: f.method } : {}),
        ...(f.cash_session_id ? { cash_session_id: f.cash_session_id } : {}),
        include_voided: f.include_voided,
        page: f.page,
        size: f.size,
      },
      signal,
    });
    return data;
  },

  void: async (id: string, reason: string): Promise<Sale> => {
    const { data } = await apiClient.post<Sale>(`/sales/${id}/void`, { reason });
    return data;
  },

  ticketPdf: async (id: string): Promise<Blob> => {
    try {
      const { data } = await apiClient.get<Blob>(`/sales/${id}/ticket.pdf`, { responseType: "blob", timeout: 30_000 });
      return data;
    } catch (err) {
      return unwrapBlobError(err);
    }
  },

  /** Enlace wa.me con el comprobante. Sin `phone` usa el teléfono del cliente. */
  whatsapp: async (id: string, phone?: string): Promise<WhatsAppLink> => {
    const { data } = await apiClient.get<WhatsAppLink>(`/sales/${id}/whatsapp`, { params: phone ? { phone } : undefined });
    return data;
  },
};
