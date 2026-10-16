/**
 * Formato de montos. La API envía los Decimal como texto ("25000.00"); aquí solo se
 * formatean para mostrar: los cálculos de dinero los hace siempre el servidor.
 */
const formatters = new Map<string, Intl.NumberFormat>();

function formatter(currency: string): Intl.NumberFormat {
  let f = formatters.get(currency);
  if (!f) {
    try {
      f = new Intl.NumberFormat("es-CR", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch {
      // Código de moneda desconocido: número simple con el código como prefijo.
      const plain = new Intl.NumberFormat("es-CR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      f = { format: (n: number) => `${currency} ${plain.format(n)}` } as Intl.NumberFormat;
    }
    formatters.set(currency, f);
  }
  return f;
}

/** "25000.00" → "₡25 000,00". "—" si es nulo o inválido. */
export function formatMoney(value: string | number | null | undefined, currency = "CRC"): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(n)) return "—";
  return formatter(currency).format(n);
}

/** ¿El monto (texto de la API) es mayor que cero? */
export function isPositiveAmount(value: string | null | undefined): boolean {
  return value !== null && value !== undefined && Number(value) > 0;
}
