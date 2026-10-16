/** Acepta coma o punto decimal ("82,5" → "82.5"), como se escribe en Costa Rica. */
export function normalizeDecimal(value: string): string {
  return value.trim().replace(",", ".");
}

/** ¿Es un número positivo con hasta `maxDecimals` decimales? */
export function isDecimal(value: string, maxDecimals = 2): boolean {
  return new RegExp(`^\\d+(\\.\\d{1,${maxDecimals}})?$`).test(normalizeDecimal(value));
}

export function toNumber(value: string): number {
  return Number(normalizeDecimal(value));
}

/** Formatea un decimal de la API para mostrarlo ("82.50" → "82,5"); "—" si es nulo. */
export function formatNumber(
  value: string | number | null | undefined,
  { min = 0, max = 2 }: { min?: number; max?: number } = {}
): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("es-CR", { minimumFractionDigits: min, maximumFractionDigits: max });
}

/** "82.50" → "82.5" para precargar un campo de edición sin ceros sobrantes. */
export function trimDecimal(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "";
  return String(Number(value));
}
