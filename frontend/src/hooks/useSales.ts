import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { salesService } from "@/services/sales.service";
import type { SaleCreatePayload, SaleFilters } from "@/types";

/** Una venta o su anulación cambian: stock, historial de ventas, caja del día y del turno. */
function invalidateAfterSale(qc: QueryClient) {
  return Promise.all([
    qc.invalidateQueries({ queryKey: queryKeys.sales.all }),
    qc.invalidateQueries({ queryKey: queryKeys.products.all }),
    qc.invalidateQueries({ queryKey: queryKeys.payments.all }), // la caja del día vive bajo "payments"
    qc.invalidateQueries({ queryKey: queryKeys.cashSessions.all }),
    qc.invalidateQueries({ queryKey: queryKeys.dashboard }),
    qc.invalidateQueries({ queryKey: queryKeys.collections.all }),
    qc.invalidateQueries({ queryKey: queryKeys.reports.all }),
  ]);
}

export function useSales(f: SaleFilters) {
  return useQuery({
    queryKey: queryKeys.sales.list(f),
    queryFn: ({ signal }) => salesService.list(f, signal),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    meta: { silent: true },
  });
}

export function useCreateSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaleCreatePayload) => salesService.create(payload),
    meta: { silent: true },
    onSuccess: () => invalidateAfterSale(qc),
  });
}

export function useVoidSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => salesService.void(id, reason),
    meta: { silent: true },
    onSuccess: () => invalidateAfterSale(qc),
  });
}
