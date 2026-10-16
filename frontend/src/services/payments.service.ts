import { apiClient } from "@/lib/axios";
import { unwrapBlobError } from "@/lib/pdf";
import type {
  CashSummary, MembershipHistoryItem, Payment, PaymentCreatePayload, PaymentFilters, PaymentListResponse,
  WhatsAppLink,
} from "@/types";

export const paymentsService = {
  list: async (filters: PaymentFilters, signal?: AbortSignal): Promise<PaymentListResponse> => {
    const { data } = await apiClient.get<PaymentListResponse>("/payments", {
      params: {
        ...(filters.date_from ? { date_from: filters.date_from } : {}),
        ...(filters.date_to ? { date_to: filters.date_to } : {}),
        ...(filters.method ? { method: filters.method } : {}),
        ...(filters.member_id ? { member_id: filters.member_id } : {}),
        include_voided: filters.include_voided,
        page: filters.page,
        size: filters.size,
      },
      signal,
    });
    return data;
  },

  get: async (id: string, signal?: AbortSignal): Promise<Payment> => {
    const { data } = await apiClient.get<Payment>(`/payments/${id}`, { signal });
    return data;
  },

  /** Registra el cobro: crea la membresía, el comprobante y actualiza el estado del socio. */
  create: async (payload: PaymentCreatePayload): Promise<Payment> => {
    const { data } = await apiClient.post<Payment>("/payments", payload);
    return data;
  },

  /** Anulación (solo administradores; solo el último pago del socio). */
  void: async (id: string, reason: string): Promise<Payment> => {
    const { data } = await apiClient.post<Payment>(`/payments/${id}/void`, { reason });
    return data;
  },

  /** Cierre de caja del día (por defecto, hoy en la zona horaria del gimnasio). */
  cashSummary: async (day: string | undefined, signal?: AbortSignal): Promise<CashSummary> => {
    const { data } = await apiClient.get<CashSummary>("/payments/cash-summary", {
      params: day ? { date: day } : undefined,
      signal,
    });
    return data;
  },

  /** PDF del comprobante como Blob (la descarga lleva el token, por eso no se usa un <a href> directo). */
  receiptPdf: async (id: string): Promise<Blob> => {
    try {
      const { data } = await apiClient.get<Blob>(`/payments/${id}/receipt.pdf`, {
        responseType: "blob",
        timeout: 30_000,
      });
      return data;
    } catch (err) {
      return unwrapBlobError(err);
    }
  },

  /** Enlace wa.me con el comprobante. Sin `phone` usa el teléfono del socio. */
  whatsapp: async (id: string, phone?: string): Promise<WhatsAppLink> => {
    const { data } = await apiClient.get<WhatsAppLink>(`/payments/${id}/whatsapp`, { params: phone ? { phone } : undefined });
    return data;
  },

  memberships: async (memberId: string, signal?: AbortSignal): Promise<MembershipHistoryItem[]> => {
    const { data } = await apiClient.get<MembershipHistoryItem[]>(`/members/${memberId}/memberships`, { signal });
    return data;
  },
};
