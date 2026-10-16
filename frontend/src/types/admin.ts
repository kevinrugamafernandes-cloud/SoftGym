import type { Member } from "./members";
import type { Payment, PaymentMethod } from "./payments";

// ── Configuración del negocio ─────────────────────────────────────────────────
export interface GymSettings {
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  whatsapp_phone: string | null;
  email: string | null;
  address: string | null;
  receipt_message: string | null;
  overdue_message: string;
  expiring_message: string;
  currency: string;
  timezone: string;
  placeholders: string[];
}

export type GymSettingsUpdate = Partial<Omit<GymSettings, "currency" | "timezone" | "placeholders">>;

// ── Inscripción con cobro ─────────────────────────────────────────────────────
export interface EnrollmentPayload {
  member: {
    identification: string;
    first_name: string;
    last_name: string;
    birth_date?: string | null;
    gender?: string | null;
    phone?: string | null;
    email?: string | null;
    notes?: string | null;
    joined_at?: string | null;
  };
  payment: {
    plan_id: string;
    amount?: string;
    method: PaymentMethod;
    reference?: string | null;
    notes?: string | null;
  };
}

export interface EnrollmentResult {
  member: Member;
  payment: Payment;
}

// ── Cobranza (morosos) ────────────────────────────────────────────────────────
export type CollectionState = "vencida" | "por_vencer";

export interface CollectionItem {
  member_id: string;
  full_name: string;
  identification: string;
  phone: string | null;
  plan_name: string;
  end_date: string;
  days: number;
  state: CollectionState;
  label: string;
  last_reminder_at: string | null;
  whatsapp_url: string | null;
  message: string;
}

export interface CollectionList {
  items: CollectionItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
  overdue_count: number;
  expiring_count: number;
}

// ── Reportes contables ────────────────────────────────────────────────────────
export type DocType = "membresia" | "venta";

export interface TaxLine {
  rate: string;
  base: string;
  tax: string;
}

export interface SalesBookRow {
  date: string;
  doc_type: DocType;
  document: string;
  customer: string | null;
  identification: string | null;
  detail: string;
  method: PaymentMethod;
  reference: string | null;
  cashier: string | null;
  taxes: TaxLine[];
  subtotal: string;
  tax_total: string;
  total: string;
  voided: boolean;
  void_reason: string | null;
}

export interface ReportSummary {
  currency: string;
  date_from: string;
  date_to: string;
  count: number;
  subtotal: string;
  tax_total: string;
  total: string;
  by_rate: { rate: string; base: string; tax: string; total: string }[];
  by_type: { doc_type: DocType; count: number; subtotal: string; tax_total: string; total: string }[];
  by_method: { method: PaymentMethod; count: number; total: string }[];
  by_day: { date: string; memberships: string; store: string; tax_total: string; total: string }[];
  voided_count: number;
  voided_total: string;
  cash_sessions: {
    count: number;
    open_count: number;
    expected_total: string;
    counted_total: string;
    difference_total: string;
    shortages_total: string;
    overages_total: string;
  };
}

export interface SalesBook {
  summary: ReportSummary;
  rows: SalesBookRow[];
}

export interface MonthlyReport {
  year: number;
  month: number;
  label: string;
  date_from: string;
  date_to: string;
  status: "en_curso" | "abierto" | "cerrado";
  can_close: boolean;
  close_blockers: string[];
  closed_at: string | null;
  closed_by_name: string | null;
  notes: string | null;
  summary: ReportSummary;
}

export interface MonthlyCloseItem {
  id: string;
  year: number;
  month: number;
  label: string;
  closed_at: string;
  closed_by_name: string | null;
  total: string;
  tax_total: string;
}

// ── Panel principal ───────────────────────────────────────────────────────────
export interface DashboardSummary {
  date: string;
  currency: string;
  today_total: string;
  today_memberships: string;
  today_store: string;
  today_payments_count: number;
  today_sales_count: number;
  month_total: string;
  month_tax: string;
  members_active: number;
  members_expiring: number;
  members_overdue: number;
  members_inactive: number;
  members_new_month: number;
  low_stock_count: number;
  open_sessions: { cashier_name: string; opened_at: string; expected_cash: string }[];
  my_session_open: boolean | null;
}
