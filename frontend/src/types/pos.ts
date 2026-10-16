import type { PaymentMethod } from "./payments";

// ── Sesiones de caja ──────────────────────────────────────────────────────────

export type CashSessionStatus = "abierta" | "cerrada";

export interface Cashier {
  id: string;
  full_name: string;
}

export interface SessionMethodTotal {
  method: PaymentMethod;
  payments_count: number;
  payments_total: string;
  sales_count: number;
  sales_total: string;
  total: string;
}

/** Movimientos del turno calculados en vivo (sin anulados). */
export interface CashSessionSummary {
  payments_count: number;
  payments_total: string;
  sales_count: number;
  sales_total: string;
  sales_tax_total: string;
  total: string;
  by_method: SessionMethodTotal[];
  cash_payments_total: string;
  cash_sales_total: string;
  /** Fondo inicial + efectivo cobrado. */
  expected_cash: string;
  voided_count: number;
  voided_total: string;
}

export interface CashSession {
  id: string;
  cashier: Cashier;
  status: CashSessionStatus;
  business_date: string;
  opened_at: string;
  opening_float: string;
  opening_notes: string | null;
  closed_at: string | null;
  closed_by_name: string | null;
  /** Instantánea del cierre (no cambia aunque luego se anule algo). */
  cash_payments_total: string | null;
  cash_sales_total: string | null;
  expected_cash: string | null;
  counted_cash: string | null;
  /** contado − esperado: positivo = sobrante, negativo = faltante. */
  difference: string | null;
  closing_notes: string | null;
  currency: string;
  summary: CashSessionSummary;
}

export interface CashSessionListItem {
  id: string;
  cashier: Cashier;
  status: CashSessionStatus;
  business_date: string;
  opened_at: string;
  closed_at: string | null;
  opening_float: string;
  expected_cash: string | null;
  counted_cash: string | null;
  difference: string | null;
}

export interface CashSessionList {
  items: CashSessionListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface CashSessionFilters {
  date_from: string;
  date_to: string;
  status: CashSessionStatus | "";
  page: number;
  size: number;
}

// ── Productos e inventario ────────────────────────────────────────────────────

export interface Product {
  id: string;
  name: string;
  sku: string | null;
  category: string | null;
  description: string | null;
  /** Precio final con IVA incluido. */
  price: string;
  cost: string | null;
  tax_rate: string;
  cabys_code: string | null;
  stock: number;
  min_stock: number;
  is_active: boolean;
  low_stock: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductList {
  items: Product[];
  total: number;
  page: number;
  size: number;
  pages: number;
  low_stock_count: number;
}

export interface ProductFilters {
  search: string;
  category: string;
  active_only: boolean;
  low_stock: boolean;
  page: number;
  size: number;
}

export interface ProductPayload {
  name: string;
  sku: string | null;
  category: string | null;
  description: string | null;
  price: string;
  cost: string | null;
  tax_rate: string;
  cabys_code: string | null;
  min_stock: number;
  is_active?: boolean;
  initial_stock?: number;
}

export type StockChangePayload =
  | { kind: "entrada"; quantity: number; unit_cost?: string | null; notes?: string | null }
  | { kind: "ajuste"; counted_stock: number; notes: string };

export type MovementKind = "inicial" | "entrada" | "venta" | "anulacion_venta" | "ajuste";

export interface InventoryMovement {
  id: string;
  kind: MovementKind;
  quantity: number;
  stock_after: number;
  unit_cost: string | null;
  sale_id: string | null;
  sale_code: string | null;
  notes: string | null;
  user_name: string | null;
  created_at: string;
}

export interface MovementList {
  items: InventoryMovement[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// ── Ventas ────────────────────────────────────────────────────────────────────

export interface SaleItem {
  product_id: string;
  product_name: string;
  cabys_code: string | null;
  quantity: number;
  unit_price: string;
  tax_rate: string;
  line_subtotal: string;
  line_tax: string;
  line_total: string;
}

export interface TaxBreakdown {
  rate: string;
  base: string;
  tax: string;
}

export interface Sale {
  id: string;
  sale_number: number;
  sale_code: string;
  sale_date: string;
  created_at: string;
  cash_session_id: string;
  cashier_name: string | null;
  customer: { member_id: string | null; name: string | null; phone: string | null };
  method: PaymentMethod;
  reference: string | null;
  items: SaleItem[];
  taxes: TaxBreakdown[];
  subtotal: string;
  tax_total: string;
  total: string;
  notes: string | null;
  is_voided: boolean;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
}

export interface SaleList {
  items: Sale[];
  total: number;
  page: number;
  size: number;
  pages: number;
  totals: {
    active_count: number;
    active_total: string;
    active_tax: string;
    voided_count: number;
    voided_total: string;
  };
}

export interface SaleFilters {
  date_from: string;
  date_to: string;
  method: PaymentMethod | "";
  cash_session_id: string;
  include_voided: boolean;
  page: number;
  size: number;
}

export interface SaleCreatePayload {
  items: { product_id: string; quantity: number }[];
  method: PaymentMethod;
  reference?: string | null;
  member_id?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  notes?: string | null;
}

export interface WhatsAppLink {
  phone: string;
  url: string;
  message: string;
}
