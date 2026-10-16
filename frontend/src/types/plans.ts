export interface Plan {
  id: string;
  name: string;
  description: string | null;
  duration_days: number;
  /** Decimal serializado como texto por la API, p. ej. "25000.00". */
  price: string;
  /** IVA incluido en el precio (13 % general). */
  tax_rate: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlanCreatePayload {
  name: string;
  description?: string | null;
  duration_days: number;
  price: string;
  tax_rate?: string;
  is_active?: boolean;
}

export type PlanUpdatePayload = Partial<PlanCreatePayload>;
