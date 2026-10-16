import type { Product } from "@/types";

export interface CartLine {
  product: Product;
  quantity: number;
}

export type CartAction =
  | { type: "add"; product: Product; quantity?: number }
  | { type: "set"; productId: string; quantity: number }
  | { type: "remove"; productId: string }
  | { type: "refresh"; products: Product[] }
  | { type: "clear" };

export const MAX_QTY = 999;

/** Carrito: una línea por producto, en el orden en que se agregó. */
export function cartReducer(state: CartLine[], action: CartAction): CartLine[] {
  switch (action.type) {
    case "add": {
      const qty = action.quantity ?? 1;
      const existing = state.find((l) => l.product.id === action.product.id);
      if (existing) {
        return state.map((l) => l.product.id === action.product.id
          ? { product: action.product, quantity: Math.min(l.quantity + qty, MAX_QTY) } : l);
      }
      return [...state, { product: action.product, quantity: Math.min(qty, MAX_QTY) }];
    }
    case "set":
      if (action.quantity <= 0) return state.filter((l) => l.product.id !== action.productId);
      return state.map((l) => l.product.id === action.productId ? { ...l, quantity: Math.min(action.quantity, MAX_QTY) } : l);
    case "remove":
      return state.filter((l) => l.product.id !== action.productId);
    case "refresh": {
      // Stock y precio actualizados desde el servidor (otra caja pudo vender).
      const byId = new Map(action.products.map((p) => [p.id, p]));
      return state.map((l) => ({ ...l, product: byId.get(l.product.id) ?? l.product }));
    }
    case "clear":
      return [];
  }
}

const round2 = (n: number) => Math.round(n * 100) / 100;

/**
 * Vista previa de totales con la MISMA regla del servidor (precio con IVA incluido; desglose por
 * línea redondeado al céntimo). Es informativa: el comprobante usa el cálculo del servidor.
 */
export function cartTotals(lines: CartLine[]) {
  let total = 0;
  let tax = 0;
  for (const l of lines) {
    const lineTotal = round2(Number(l.product.price) * l.quantity);
    const rate = Number(l.product.tax_rate);
    const base = rate > 0 ? round2(lineTotal / (1 + rate / 100)) : lineTotal;
    total += lineTotal;
    tax += lineTotal - base;
  }
  total = round2(total);
  tax = round2(tax);
  return { total, tax, subtotal: round2(total - tax), items: lines.reduce((a, l) => a + l.quantity, 0) };
}

/** Líneas que piden más de lo que hay (según el último stock conocido). */
export function overStock(lines: CartLine[]): CartLine[] {
  return lines.filter((l) => l.quantity > l.product.stock);
}
