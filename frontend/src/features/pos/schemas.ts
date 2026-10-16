import { z } from "zod";
import { isDecimal, normalizeDecimal, trimDecimal } from "@/lib/numbers";
import type { Product, ProductPayload } from "@/types";

/** Tarifas de IVA de Costa Rica (Ley 9635): general 13 %, reducidas 4/2/1 % y exento. */
export const TAX_RATES = [
  { value: "13", label: "13 % (general)" },
  { value: "4", label: "4 %" },
  { value: "2", label: "2 %" },
  { value: "1", label: "1 %" },
  { value: "0", label: "Exento (0 %)" },
] as const;

const money = (msg: string, required = true) =>
  z.string().trim()
    .refine((v) => (required ? v !== "" : true), msg)
    .refine((v) => v === "" || isDecimal(v, 2), "Monto inválido (use números, con hasta 2 decimales)")
    .refine((v) => v === "" || Number(normalizeDecimal(v)) <= 99_999_999.99, "El monto es demasiado alto");

const intField = (msg: string) =>
  z.string().trim().refine((v) => /^\d{1,7}$/.test(v), msg);

export const productFormSchema = z.object({
  name: z.string().trim().min(2, "El nombre debe tener al menos 2 caracteres").max(120, "Máximo 120 caracteres"),
  sku: z.string().trim().max(40, "Máximo 40 caracteres"),
  category: z.string().trim().max(60, "Máximo 60 caracteres"),
  price: money("Indique el precio de venta"),
  cost: money("", false),
  tax_rate: z.enum(["13", "4", "2", "1", "0"]),
  cabys_code: z.string().trim().refine((v) => v === "" || /^\d{13}$/.test(v), "El código CABYS tiene 13 dígitos"),
  min_stock: intField("Indique un número entero (0 o más)"),
  initial_stock: intField("Indique un número entero (0 o más)"),
  description: z.string().trim().max(1000, "Máximo 1000 caracteres"),
});
export type ProductFormValues = z.infer<typeof productFormSchema>;

export const emptyProductForm: ProductFormValues = {
  name: "", sku: "", category: "", price: "", cost: "", tax_rate: "13", cabys_code: "", min_stock: "3",
  initial_stock: "0", description: "",
};

export function productToForm(p: Product): ProductFormValues {
  const rate = String(Number(p.tax_rate));
  return {
    name: p.name, sku: p.sku ?? "", category: p.category ?? "", price: trimDecimal(p.price), cost: trimDecimal(p.cost),
    tax_rate: (["13", "4", "2", "1", "0"].includes(rate) ? rate : "13") as ProductFormValues["tax_rate"],
    cabys_code: p.cabys_code ?? "", min_stock: String(p.min_stock), initial_stock: "0", description: p.description ?? "",
  };
}

export function toProductPayload(v: ProductFormValues, creating: boolean): ProductPayload {
  return {
    name: v.name, sku: v.sku || null, category: v.category || null, description: v.description || null,
    price: normalizeDecimal(v.price), cost: v.cost ? normalizeDecimal(v.cost) : null, tax_rate: v.tax_rate,
    cabys_code: v.cabys_code || null, min_stock: Number(v.min_stock),
    ...(creating ? { initial_stock: Number(v.initial_stock) } : {}),
  };
}

/** Margen bruto sobre el precio SIN IVA: (base − costo) / base. */
export function marginPct(p: Pick<Product, "price" | "cost" | "tax_rate">): number | null {
  if (!p.cost) return null;
  const base = Number(p.price) / (1 + Number(p.tax_rate) / 100);
  return base > 0 ? ((base - Number(p.cost)) / base) * 100 : null;
}
