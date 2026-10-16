import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { measurementsService } from "@/services/measurements.service";
import type { MeasurementCreatePayload, MeasurementUpdatePayload } from "@/types";

/** Historial evolutivo del socio (más reciente primero). */
export function useMeasurements(memberId: string | undefined, limit = 50) {
  return useQuery({
    queryKey: queryKeys.measurements.list(memberId ?? "", limit),
    queryFn: ({ signal }) => measurementsService.list(memberId as string, limit, signal),
    enabled: Boolean(memberId),
    placeholderData: keepPreviousData,
    meta: { silent: true },
  });
}

export function useCreateMeasurement(memberId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MeasurementCreatePayload) => measurementsService.create(memberId, payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.measurements.forMember(memberId) }),
  });
}

export function useUpdateMeasurement(memberId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: MeasurementUpdatePayload }) =>
      measurementsService.update(memberId, id, payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.measurements.forMember(memberId) }),
  });
}

export function useDeleteMeasurement(memberId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => measurementsService.remove(memberId, id),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.measurements.forMember(memberId) }),
  });
}
