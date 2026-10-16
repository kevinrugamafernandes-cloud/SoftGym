import { apiClient } from "@/lib/axios";
import type { MovementList, Product, ProductFilters, ProductList, ProductPayload, StockChangePayload } from "@/types";

export const productsService = {
  list: async (f: ProductFilters, signal?: AbortSignal): Promise<ProductList> => {
    const search = f.search.trim();
    const { data } = await apiClient.get<ProductList>("/products", {
      params: {
        ...(search ? { search } : {}),
        ...(f.category ? { category: f.category } : {}),
        ...(f.active_only ? { active_only: true } : {}),
        ...(f.low_stock ? { low_stock: true } : {}),
        page: f.page,
        size: f.size,
      },
      signal,
    });
    return data;
  },

  categories: async (signal?: AbortSignal): Promise<string[]> => {
    const { data } = await apiClient.get<string[]>("/products/categories", { signal });
    return data;
  },

  create: async (payload: ProductPayload): Promise<Product> => {
    const { data } = await apiClient.post<Product>("/products", payload);
    return data;
  },

  update: async (id: string, payload: Partial<ProductPayload>): Promise<Product> => {
    const { data } = await apiClient.patch<Product>(`/products/${id}`, payload);
    return data;
  },

  changeStock: async (id: string, payload: StockChangePayload): Promise<Product> => {
    const { data } = await apiClient.post<Product>(`/products/${id}/stock`, payload);
    return data;
  },

  movements: async (id: string, page: number, signal?: AbortSignal): Promise<MovementList> => {
    const { data } = await apiClient.get<MovementList>(`/products/${id}/movements`, { params: { page, size: 15 }, signal });
    return data;
  },
};
