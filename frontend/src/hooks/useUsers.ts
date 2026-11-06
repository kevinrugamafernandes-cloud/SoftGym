import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { usersService } from "@/services/users.service";
import type { StaffUserCreate, StaffUserUpdate } from "@/types";

export function useUsers() {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: ({ signal }) => usersService.list(signal),
    meta: { silent: true },
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StaffUserCreate) => usersService.create(payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.users }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StaffUserUpdate }) => usersService.update(id, payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.users }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) => usersService.resetPassword(id, password),
    meta: { silent: true },
  });
}
