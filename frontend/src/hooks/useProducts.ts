import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-keys";
import { productsService } from "@/services/products.service";
import type { ProductFilters, ProductPayload, StockChangePayload } from "@/types";

export function useProducts(f: ProductFilters) {
  return useQuery({
    queryKey: queryKeys.products.list(f),
    queryFn: ({ signal }) => productsService.list(f, signal),
    placeholderData: keepPreviousData,
    staleTime: 10_000, // el stock cambia con cada venta
    meta: { silent: true },
  });
}

export function useProductCategories() {
  return useQuery({
    queryKey: queryKeys.products.categories,
    queryFn: ({ signal }) => productsService.categories(signal),
    staleTime: 60_000,
    meta: { silent: true },
  });
}

export function useProductMovements(id: string | null, page: number) {
  return useQuery({
    queryKey: queryKeys.products.movements(id ?? "", page),
    queryFn: ({ signal }) => productsService.movements(id as string, page, signal),
    enabled: Boolean(id),
    placeholderData: keepPreviousData,
    meta: { silent: true },
  });
}

export function useSaveProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id?: string; payload: ProductPayload }) =>
      id ? productsService.update(id, payload) : productsService.create(payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.products.all }),
  });
}

export function useToggleProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => productsService.update(id, { is_active }),
    meta: { errorTitle: "No se pudo actualizar el producto" },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.products.all }),
  });
}

export function useChangeStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StockChangePayload }) => productsService.changeStock(id, payload),
    meta: { silent: true },
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.products.all }),
  });
}
