import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { getErrorMessage, getErrorStatus } from "@/lib/axios";
import { toast } from "@/hooks/useToast";

declare module "@tanstack/react-query" {
  interface Register {
    /** `silent: true` → el error NO genera Toast global (el componente lo maneja). */
    queryMeta: { silent?: boolean; errorTitle?: string };
    mutationMeta: { silent?: boolean; errorTitle?: string };
  }
}

/** Un 401 lo gestiona el interceptor de Axios (redirige a /login): sin Toast. */
function notify(error: unknown, title: string) {
  if (getErrorStatus(error) === 401) return;
  toast({ variant: "destructive", title, description: getErrorMessage(error) });
}

export const queryClient = new QueryClient({
  // Manejo GLOBAL de errores: cualquier consulta o mutación que falle muestra un Toast
  // con el campo `detail` de la respuesta, salvo que declare meta.silent.
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.meta?.silent) return;
      notify(error, query.meta?.errorTitle ?? "No se pudo cargar la información");
    },
  }),
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (mutation.meta?.silent) return;
      notify(error, mutation.meta?.errorTitle ?? "No se pudo completar la acción");
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutos
      retry: (failureCount, error: unknown) => {
        // Los errores 4xx (401/403/404/422…) no se arreglan reintentando.
        const status = getErrorStatus(error);
        if (status !== undefined && status >= 400 && status < 500) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
});
