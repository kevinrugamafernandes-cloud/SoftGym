/** Los decimales llegan como texto ("82.50"); null si el dato no se registró. */
export interface Measurement {
  id: string;
  member_id: string;
  recorded_at: string;
  weight_kg: string | null;
  height_cm: string | null;
  /** Calculado por el servidor: nunca se calcula ni se envía desde el cliente. */
  bmi: string | null;
  /** Clasificación OMS calculada por el servidor ("Peso normal", "Sobrepeso"…). */
  bmi_category: string | null;
  body_fat_pct: string | null;
  muscle_pct: string | null;
  chest_cm: string | null;
  waist_cm: string | null;
  hips_cm: string | null;
  arms_cm: string | null;
  thighs_cm: string | null;
  calves_cm: string | null;
  notes: string | null;
  created_at: string;
}

export interface MeasurementHistory {
  member_id: string;
  items: Measurement[];
  total: number;
}

export interface MeasurementValues {
  weight_kg?: string | null;
  height_cm?: string | null;
  body_fat_pct?: string | null;
  muscle_pct?: string | null;
  chest_cm?: string | null;
  waist_cm?: string | null;
  hips_cm?: string | null;
  arms_cm?: string | null;
  thighs_cm?: string | null;
  calves_cm?: string | null;
  notes?: string | null;
}

export interface MeasurementCreatePayload extends MeasurementValues {
  /** ISO 8601; si se omite, el servidor usa la fecha y hora actuales. */
  recorded_at?: string;
}

export type MeasurementUpdatePayload = MeasurementValues;
