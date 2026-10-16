import { getErrorMessage, getErrorStatus } from "@/lib/axios";
import { toast } from "@/hooks/useToast";

/**
 * Muestra un Toast con el `detail` del backend (en español) y devuelve el mensaje
 * para que el formulario también lo conserve en su estado (aviso en línea).
 * Un 401 no genera Toast: el interceptor ya redirige al inicio de sesión.
 */
export function reportError(error: unknown, title: string): string {
  const message = getErrorMessage(error);
  if (getErrorStatus(error) !== 401) {
    toast({ variant: "destructive", title, description: message });
  }
  return message;
}
