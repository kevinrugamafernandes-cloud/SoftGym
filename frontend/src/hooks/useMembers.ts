import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { membersService } from "@/services/members.service";
import type { MemberCreatePayload, MemberFilters, MemberUpdatePayload } from "@/types";

/** Listado paginado con filtros. Mantiene la página anterior visible mientras carga la nueva. */
export function useMembers(filters: MemberFilters) {
  return useQuery({
    queryKey: queryKeys.members.list(filters),
    queryFn: ({ signal }) => membersService.list(filters, signal),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    meta: { silent: true }, // la página muestra el error en línea con botón "Reintentar"
  });
}

export function useMember(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.members.detail(id ?? ""),
    queryFn: ({ signal }) => membersService.get(id as string, signal),
    enabled: Boolean(id),
    meta: { silent: true },
  });
}

/**
 * Fácil Inscripción: consulta la cédula en el backend (que consulta a Hacienda).
 * Es una consulta (no mutación) para que React Query cachee por cédula y descarte
 * respuestas obsoletas. `retry: false`: Hacienda bloquea la IP ante consultas repetidas.
 */
export function useCedulaLookup(identification: string | null) {
  return useQuery({
    queryKey: queryKeys.members.cedula(identification ?? ""),
    queryFn: ({ signal }) => membersService.lookupCedula(identification as string, signal),
    enabled: Boolean(identification),
    retry: false,
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    meta: { silent: true },
  });
}

// Las mutaciones son `silent`: cada formulario/diálogo muestra el error en línea Y con
// Toast mediante reportError(), para no duplicar avisos ni perder el contexto.
export function useCreateMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: MemberCreatePayload) => membersService.create(payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.members.all }),
  });
}

export function useUpdateMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: MemberUpdatePayload }) =>
      membersService.update(id, payload),
    meta: { silent: true },
    onSuccess: (member) => {
      qc.setQueryData(queryKeys.members.detail(member.id), member);
      return qc.invalidateQueries({ queryKey: queryKeys.members.all });
    },
  });
}

export function useDeleteMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => membersService.remove(id),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.members.all }),
  });
}

export function useRestoreMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => membersService.restore(id),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.members.all }),
  });
}
