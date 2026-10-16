import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePermissions } from "@/features/auth";
import { queryKeys } from "@/lib/query-keys";
import { collectionsService, enrollmentService, reportsService, settingsService } from "@/services/admin.service";
import type { CollectionState, EnrollmentPayload, GymSettingsUpdate } from "@/types";

export function useGymSettings() {
  return useQuery({
    queryKey: queryKeys.settings,
    queryFn: ({ signal }) => settingsService.get(signal),
    staleTime: 5 * 60_000,
    meta: { silent: true },
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: GymSettingsUpdate) => settingsService.update(payload),
    meta: { silent: true },
    onSuccess: (s) => {
      qc.setQueryData(queryKeys.settings, s);
      return qc.invalidateQueries({ queryKey: queryKeys.collections.all }); // los mensajes cambian
    },
  });
}

export function useEnroll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: EnrollmentPayload) => enrollmentService.enroll(payload),
    meta: { silent: true },
    onSuccess: () => Promise.all([
      qc.invalidateQueries({ queryKey: queryKeys.members.all }),
      qc.invalidateQueries({ queryKey: queryKeys.payments.all }),
      qc.invalidateQueries({ queryKey: queryKeys.cashSessions.all }),
      qc.invalidateQueries({ queryKey: queryKeys.dashboard }),
    ]),
  });
}

export function useCollections(f: { state: CollectionState; search: string; page: number; size: number }) {
  return useQuery({
    queryKey: queryKeys.collections.list(f),
    queryFn: ({ signal }) => collectionsService.list(f, signal),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    meta: { silent: true },
  });
}

export function useLogReminder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, kind }: { memberId: string; kind: CollectionState }) => collectionsService.logReminder(memberId, kind),
    meta: { silent: true }, // registrar el envío es secundario: si falla, el mensaje igual se abrió
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.collections.all }),
  });
}

export function useDashboard() {
  const { can } = usePermissions();
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: ({ signal }) => reportsService.dashboard(signal),
    enabled: can("payments.view"),
    staleTime: 30_000,
    refetchInterval: 60_000,
    meta: { silent: true },
  });
}

export function useSalesBook(dateFrom: string, dateTo: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reports.salesBook(dateFrom, dateTo),
    queryFn: ({ signal }) => reportsService.salesBook(dateFrom, dateTo, signal),
    enabled: enabled && Boolean(dateFrom && dateTo),
    placeholderData: keepPreviousData,
    meta: { silent: true },
  });
}

export function useMonthlyReport(year: number, month: number) {
  return useQuery({
    queryKey: queryKeys.reports.monthly(year, month),
    queryFn: ({ signal }) => reportsService.monthly(year, month, signal),
    placeholderData: keepPreviousData,
    meta: { silent: true },
  });
}

export function useMonthlyCloses() {
  return useQuery({
    queryKey: queryKeys.reports.closes,
    queryFn: ({ signal }) => reportsService.closes(signal),
    meta: { silent: true },
  });
}

export function useCloseMonth() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ year, month, notes }: { year: number; month: number; notes: string | null }) =>
      reportsService.closeMonth(year, month, notes),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.reports.all }),
  });
}
