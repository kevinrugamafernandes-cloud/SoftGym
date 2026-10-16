import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePermissions } from "@/features/auth";
import { queryKeys } from "@/lib/query-keys";
import { cashSessionsService } from "@/services/cash-sessions.service";
import type { CashSessionFilters } from "@/types";

/**
 * Caja abierta del usuario (o null). Solo para roles que cobran; se refresca cada minuto para
 * que el esperado en efectivo del indicador se mantenga al día.
 */
export function useCurrentCashSession() {
  const { can } = usePermissions();
  return useQuery({
    queryKey: queryKeys.cashSessions.current,
    queryFn: ({ signal }) => cashSessionsService.current(signal),
    enabled: can("cash.view"),
    staleTime: 15_000,
    refetchInterval: 60_000,
    meta: { silent: true },
  });
}

export function useCashSession(id: string | null) {
  return useQuery({
    queryKey: queryKeys.cashSessions.detail(id ?? ""),
    queryFn: ({ signal }) => cashSessionsService.get(id as string, signal),
    enabled: Boolean(id),
    meta: { silent: true },
  });
}

export function useCashSessions(f: CashSessionFilters) {
  return useQuery({
    queryKey: queryKeys.cashSessions.list(f),
    queryFn: ({ signal }) => cashSessionsService.list(f, signal),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    meta: { silent: true },
  });
}

export function useOpenCashSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: cashSessionsService.open,
    meta: { silent: true },
    onSuccess: (session) => {
      qc.setQueryData(queryKeys.cashSessions.current, session);
      return qc.invalidateQueries({ queryKey: queryKeys.cashSessions.all });
    },
  });
}

export function useCloseCashSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, counted_cash, notes }: { id: string; counted_cash: string; notes?: string | null }) =>
      cashSessionsService.close(id, { counted_cash, notes }),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.cashSessions.all }),
  });
}
