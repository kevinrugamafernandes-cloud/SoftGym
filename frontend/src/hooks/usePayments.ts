import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { paymentsService } from "@/services/payments.service";
import type { PaymentCreatePayload, PaymentFilters } from "@/types";

/**
 * Un cobro o una anulación cambian: el historial y la caja, la membresía y el ESTADO del
 * socio (activo/por vencer/moroso). Se invalida todo lo que depende de eso.
 */
function invalidateAfterMoneyChange(qc: QueryClient, memberId: string) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: queryKeys.payments.all }),
    qc.invalidateQueries({ queryKey: queryKeys.members.all }),
    qc.invalidateQueries({ queryKey: queryKeys.memberships.forMember(memberId) }),
    qc.invalidateQueries({ queryKey: queryKeys.cashSessions.all }), // el esperado del turno cambia
    qc.invalidateQueries({ queryKey: queryKeys.dashboard }),
    qc.invalidateQueries({ queryKey: queryKeys.collections.all }),
    qc.invalidateQueries({ queryKey: queryKeys.reports.all }),
  ]);
}

export function usePayments(filters: PaymentFilters, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.payments.list(filters),
    queryFn: ({ signal }) => paymentsService.list(filters, signal),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    enabled,
    meta: { silent: true }, // la página muestra el error en línea con "Reintentar"
  });
}

export function useCashSummary(day: string) {
  return useQuery({
    queryKey: queryKeys.payments.cash(day),
    queryFn: ({ signal }) => paymentsService.cashSummary(day, signal),
    staleTime: 15_000,
    refetchInterval: 60_000, // la caja de hoy se mantiene al día si quedó abierta en recepción
    meta: { silent: true },
  });
}

export function useMemberships(memberId: string | undefined, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.memberships.forMember(memberId ?? ""),
    queryFn: ({ signal }) => paymentsService.memberships(memberId as string, signal),
    enabled: Boolean(memberId) && enabled,
    meta: { silent: true },
  });
}

// Mutaciones `silent`: cada diálogo muestra el error en línea y con Toast vía reportError().
export function useCreatePayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PaymentCreatePayload) => paymentsService.create(payload),
    meta: { silent: true },
    onSuccess: (payment) => invalidateAfterMoneyChange(qc, payment.member.id),
  });
}

export function useVoidPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => paymentsService.void(id, reason),
    meta: { silent: true },
    onSuccess: (payment) => invalidateAfterMoneyChange(qc, payment.member.id),
  });
}

/**
 * Moneda del gimnasio. La API la expone en la caja del día (y en el comprobante);
 * se reutiliza la consulta de la caja de hoy, que React Query ya tiene en caché.
 */
export function useGymCurrency(): string {
  const today = new Date();
  const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return useCashSummary(iso).data?.currency ?? "CRC";
}
