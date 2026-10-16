import type { UseQueryResult } from "@tanstack/react-query";
import { getErrorMessage, getErrorStatus } from "@/lib/axios";
import type { CedulaLookupResult } from "@/types";

/**
 * Estado visual de la consulta de cédula (Fácil Inscripción).
 *
 *  idle        → aún no se consultó (o la cédula cambió después de consultar)
 *  loading     → "Consultando en Hacienda…"
 *  found       → datos de Hacienda autocompletados (puede requerir revisión)
 *  registered  → la cédula ya pertenece a un socio (activo o dado de baja)
 *  not_found   → 404: Hacienda no la conoce → ingreso manual
 *  unavailable → 503 / timeout / sin red → ingreso manual (el formulario sigue habilitado)
 *  rejected    → 422/403: formato inválido o persona jurídica (mensaje del backend)
 */
export type LookupUiState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "found"; data: CedulaLookupResult }
  | { kind: "registered"; data: CedulaLookupResult }
  | { kind: "not_found" }
  | { kind: "unavailable" }
  | { kind: "rejected"; message: string };

export function deriveLookupState(
  requested: string | null,
  current: string,
  query: Pick<UseQueryResult<CedulaLookupResult, unknown>, "data" | "error" | "isError" | "isFetching">
): LookupUiState {
  if (!requested || requested !== current) return { kind: "idle" };
  if (query.isFetching && !query.data) return { kind: "loading" };

  if (query.data) {
    return query.data.already_registered
      ? { kind: "registered", data: query.data }
      : { kind: "found", data: query.data };
  }

  if (query.isError) {
    const status = getErrorStatus(query.error);
    if (status === 404) return { kind: "not_found" };
    // Sin respuesta (timeout / red caída) o error del servidor: el servicio no está disponible.
    if (status === undefined || status >= 500) return { kind: "unavailable" };
    return { kind: "rejected", message: getErrorMessage(query.error) };
  }
  return { kind: "idle" };
}
