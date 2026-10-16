import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { ApiError } from "@/types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// ── Request interceptor — inject Bearer token ─────────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor — normalise errors ───────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const isLoginRequest = error.config?.url?.includes("/auth/login"); // Ajusta el endpoint si difiere en tu backend
    const isAlreadyOnLoginPage = window.location.pathname === "/login";

    if (error.response?.status === 401 && !isLoginRequest && !isAlreadyOnLoginPage) {
      // Limpia el token expirado/inválido y redirige solo si estábamos en una ruta protegida
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

/**
 * Mensaje legible, SIEMPRE en español, a partir de cualquier error.
 * El backend responde {"detail": "...", "code": "..."} con `detail` ya en español;
 * si no hay respuesta (red caída, timeout) se genera un mensaje local.
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Partial<ApiError> | undefined;
    if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;

    if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") {
      return "La solicitud tardó demasiado en responder. Intente de nuevo.";
    }
    if (!error.response) {
      return "No se pudo conectar con el servidor. Verifique su conexión e intente de nuevo.";
    }
    return `Ocurrió un error inesperado (código ${error.response.status}). Intente de nuevo.`;
  }
  return "Ocurrió un error inesperado. Intente de nuevo.";
}

/** Estado HTTP del error, o undefined si no hubo respuesta (red caída, timeout). */
export function getErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

/** Código de máquina del backend (p. ej. "member_exists", "lookup_unavailable"). */
export function getErrorCode(error: unknown): string | undefined {
  if (!axios.isAxiosError(error)) return undefined;
  return (error.response?.data as Partial<ApiError> | undefined)?.code;
}

/** Errores por campo de una validación 422: [{ field: "first_name", message: "..." }]. */
export function getFieldErrors(error: unknown): { field: string; message: string }[] {
  if (!axios.isAxiosError(error)) return [];
  const errors = (error.response?.data as Partial<ApiError> | undefined)?.errors;
  return Array.isArray(errors) ? errors : [];
}

/** ¿El error es de conectividad (sin respuesta del servidor o timeout)? */
export function isNetworkError(error: unknown): boolean {
  return axios.isAxiosError(error) && !error.response;
}
