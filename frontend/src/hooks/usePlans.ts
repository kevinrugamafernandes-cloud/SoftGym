import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { plansService } from "@/services/plans.service";
import type { PlanCreatePayload, PlanUpdatePayload } from "@/types";

/** Planes de membresía. `activeOnly` = solo los que se ofrecen al inscribir. */
export function usePlans(activeOnly = false) {
  return useQuery({
    queryKey: queryKeys.plans.list(activeOnly),
    queryFn: ({ signal }) => plansService.list(activeOnly, signal),
    staleTime: 60_000,
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PlanCreatePayload) => plansService.create(payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plans.all }),
  });
}

export function useUpdatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: PlanUpdatePayload }) =>
      plansService.update(id, payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plans.all }),
  });
}

export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => plansService.remove(id),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plans.all }),
  });
}
