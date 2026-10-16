import { z } from "zod";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";

const MAX = 9_999_999_999.99;

export const amountField = (label: string) =>
  z
    .string()
    .trim()
    .min(1, `Indique ${label}`)
    .refine((v) => isDecimal(v, 2), "Monto inválido (use números, con hasta 2 decimales)")
    .refine((v) => Number(normalizeDecimal(v)) <= MAX, "El monto es demasiado alto");

export const openCashSchema = z.object({
  opening_float: amountField("el fondo inicial"),
  notes: z.string().trim().max(1000, "Máximo 1000 caracteres"),
});
export type OpenCashValues = z.infer<typeof openCashSchema>;

/** Billetes y monedas en circulación en Costa Rica (colones). */
export const CRC_DENOMINATIONS = [
  { value: 20000, label: "₡20 000", kind: "billete" },
  { value: 10000, label: "₡10 000", kind: "billete" },
  { value: 5000, label: "₡5 000", kind: "billete" },
  { value: 2000, label: "₡2 000", kind: "billete" },
  { value: 1000, label: "₡1 000", kind: "billete" },
  { value: 500, label: "₡500", kind: "moneda" },
  { value: 100, label: "₡100", kind: "moneda" },
  { value: 50, label: "₡50", kind: "moneda" },
  { value: 25, label: "₡25", kind: "moneda" },
  { value: 10, label: "₡10", kind: "moneda" },
  { value: 5, label: "₡5", kind: "moneda" },
] as const;

/** Diferencia contado − esperado redondeada al céntimo (evita 0.30000000000000004). */
export function cashDifference(counted: number, expected: number): number {
  return Math.round((counted - expected) * 100) / 100;
}
