import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { ApiError } from "@/types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// ── Sesión: el token se renueva solo mientras el usuario trabaja ─────────────
export const TOKEN_KEY = "access_token";
/** Si al token le quedan menos de estos minutos, se renueva antes de la siguiente petición. */
const RENEW_BEFORE_MS = 60 * 60 * 1000;

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Vencimiento (ms) leído del propio JWT; null si no se puede leer. */
function tokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

let renewing: Promise<void> | null = null;

/** Renueva el token una sola vez aunque haya varias peticiones a la vez. Si falla, sigue con el actual. */
function renewToken(token: string): Promise<void> {
  if (!renewing) {
    renewing = axios
      .post<{ access_token: string }>(`${BASE_URL}/api/v1/auth/refresh`, null, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 15_000,
      })
      .then(({ data }) => saveToken(data.access_token))
      .catch(() => undefined)
      .finally(() => {
        renewing = null;
      });
  }
  return renewing;
}

// ── Request interceptor — inject Bearer token ─────────────────────────────────
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    let token = localStorage.getItem(TOKEN_KEY);
    const isAuthCall = config.url?.includes("/auth/login") || config.url?.includes("/auth/refresh");
    if (token && !isAuthCall) {
      const exp = tokenExpiry(token);
      if (exp !== null && exp > Date.now() && exp - Date.now() < RENEW_BEFORE_MS) {
        await renewToken(token);
        token = localStorage.getItem(TOKEN_KEY);
      }
    }
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
      clearToken();
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
