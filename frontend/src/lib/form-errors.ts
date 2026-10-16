import type { FieldErrors, FieldValues } from "react-hook-form";

/**
 * Mensaje para el aviso superior de un formulario cuya validación falló.
 *  - Campo inválido VISIBLE  → aviso genérico (el detalle ya aparece bajo el campo).
 *  - Campo inválido OCULTO   → se detalla el mensaje: sin esto el envío fallaría en silencio.
 */
export function describeInvalidFields<T extends FieldValues>(invalidFields: FieldErrors<T>): string {
  const entries = Object.entries(invalidFields).filter(
    (entry): entry is [string, { message: string }] => typeof (entry[1] as { message?: unknown })?.message === "string"
  );
  const hidden = entries.find(([name]) => !document.querySelector(`[name="${name}"]`));
  return hidden ? `Revise el formulario: ${hidden[1].message}` : "Revise los campos marcados en rojo.";
}
