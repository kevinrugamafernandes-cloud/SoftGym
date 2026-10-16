import type { PaginatedResponse } from "./index";

/** Valores del enum payment_method_enum del backend. */
export type PaymentMethod = "efectivo" | "tarjeta" | "transferencia" | "sinpe" | "otro";

/** Membresía vigente (o la última) del socio, con días restantes ya calculados por el servidor. */
export interface MembershipSummary {
  id: string;
  plan_id: string;
  plan_name: string;
  start_date: string;
  end_date: string;
  /** 0 = vence hoy; negativo = ya venció. */
  days_remaining: number;
  days_overdue: number;
  state: "vigente" | "por_vencer" | "vencida";
  /** "Vence en 3 días", "Venció hace 5 días"… */
  label: string;
}

export interface PaymentMember {
  id: string;
  full_name: string;
  identification: string;
}

export interface PaymentPlan {
  id: string;
  name: string;
  duration_days: number;
}

/** Los montos (Decimal) llegan como texto: "25000.00". */
export interface Payment {
  id: string;
  receipt_number: number;
  receipt_code: string;
  member: PaymentMember;
  plan: PaymentPlan;
  period: { start_date: string; end_date: string };
  amount: string;
  list_price: string | null;
  discount: string;
  /** IVA incluido en `amount`. */
  tax_rate: string;
  subtotal: string;
  tax_amount: string;
  method: PaymentMethod;
  payment_date: string;
  reference: string | null;
  notes: string | null;
  registered_by_name: string | null;
  /** Turno de caja en que se cobró (null en pagos anteriores a las sesiones de caja). */
  cash_session_id: string | null;
  is_voided: boolean;
  voided_at: string | null;
  voided_by_name: string | null;
  void_reason: string | null;
  created_at: string;
}

export interface PaymentTotals {
  active_count: number;
  active_total: string;
  voided_count: number;
  voided_total: string;
}

export interface PaymentListResponse extends PaginatedResponse<Payment> {
  /** Totales de TODO el filtro, no solo de la página. */
  totals: PaymentTotals;
}

export interface PaymentFilters {
  date_from: string;
  date_to: string;
  method: PaymentMethod | "";
  member_id: string;
  include_voided: boolean;
  page: number;
  size: number;
}

export interface PaymentCreatePayload {
  member_id: string;
  plan_id: string;
  /** Omitido → se cobra el precio del plan. */
  amount?: string;
  method: PaymentMethod;
  payment_date?: string;
  reference?: string | null;
  notes?: string | null;
  confirm_duplicate?: boolean;
}

export interface MethodTotal {
  method: PaymentMethod;
  count: number;
  total: string;
}

export interface CashSummary {
  date: string;
  currency: string;
  count: number;
  total: string;
  by_method: MethodTotal[];
  voided_count: number;
  voided_total: string;
  /** Separación del total: membresías vs. tienda. */
  payments_count: number;
  payments_total: string;
  sales_count: number;
  sales_total: string;
  sales_tax_total: string;
}

export interface MembershipHistoryItem {
  id: string;
  plan_id: string;
  plan_name: string;
  start_date: string;
  end_date: string;
  status: string;
  created_at: string;
}
