import { z } from "zod";
import { isRealDate, todayISO } from "@/features/members/schemas";
import { isDecimal, normalizeDecimal, toNumber, trimDecimal } from "@/lib/numbers";
import type { Measurement, MeasurementCreatePayload, MeasurementUpdatePayload } from "@/types";

/**
 * Los límites replican los del backend (esquemas Pydantic). El IMC NO se calcula aquí:
 * lo calcula el servidor y vuelve en la respuesta.
 */
interface Range { label: string; min: number; max: number; exclusiveMin?: boolean }

const RANGES = {
  weight_kg: { label: "Peso", min: 0, max: 500, exclusiveMin: true },
  body_fat_pct: { label: "% de grasa", min: 0, max: 100 },
  muscle_pct: { label: "% de músculo", min: 0, max: 100 },
  chest_cm: { label: "Pecho", min: 0, max: 300, exclusiveMin: true },
  waist_cm: { label: "Cintura", min: 0, max: 300, exclusiveMin: true },
  hips_cm: { label: "Cadera", min: 0, max: 300, exclusiveMin: true },
  arms_cm: { label: "Brazo", min: 0, max: 150, exclusiveMin: true },
  thighs_cm: { label: "Muslo", min: 0, max: 200, exclusiveMin: true },
  calves_cm: { label: "Pantorrilla", min: 0, max: 150, exclusiveMin: true },
} satisfies Record<string, Range>;

const HEIGHT = { cm: { min: 50, max: 260 }, m: { min: 0.5, max: 2.6 } } as const;

function inRange(value: string, r: Range): boolean {
  if (!isDecimal(value)) return false;
  const n = toNumber(value);
  return (r.exclusiveMin ? n > r.min : n >= r.min) && n <= r.max;
}

const rangeMessage = (r: Range) =>
  `${r.label}: ingrese un número ${r.exclusiveMin ? "mayor que" : "desde"} ${r.min} hasta ${r.max} (máximo 2 decimales)`;

const optional = (r: Range) => z.string().refine((v) => v.trim() === "" || inRange(v, r), rangeMessage(r));

export const measurementSchema = z
  .object({
    recorded_on: z
      .string()
      .refine((v) => v === "" || (isRealDate(v) && v <= todayISO()), "La fecha de la medición no puede ser futura"),
    weight_kg: z
      .string()
      .trim()
      .min(1, "El peso es obligatorio")
      .refine((v) => inRange(v, RANGES.weight_kg), rangeMessage(RANGES.weight_kg)),
    height: z.string().trim(),
    height_unit: z.enum(["cm", "m"]),
    body_fat_pct: optional(RANGES.body_fat_pct),
    muscle_pct: optional(RANGES.muscle_pct),
    chest_cm: optional(RANGES.chest_cm),
    waist_cm: optional(RANGES.waist_cm),
    hips_cm: optional(RANGES.hips_cm),
    arms_cm: optional(RANGES.arms_cm),
    thighs_cm: optional(RANGES.thighs_cm),
    calves_cm: optional(RANGES.calves_cm),
    notes: z.string().max(1000, "Máximo 1000 caracteres"),
  })
  .superRefine((v, ctx) => {
    if (v.height === "") {
      ctx.addIssue({ code: "custom", path: ["height"], message: "La estatura es obligatoria" });
    } else {
      const h = HEIGHT[v.height_unit];
      const n = toNumber(v.height);
      if (!isDecimal(v.height) || n < h.min || n > h.max) {
        ctx.addIssue({
          code: "custom",
          path: ["height"],
          message: `Estatura inválida: ingrese un valor entre ${h.min} y ${h.max} ${v.height_unit} (máximo 2 decimales)`,
        });
      }
    }
    const fat = v.body_fat_pct.trim() !== "" && inRange(v.body_fat_pct, RANGES.body_fat_pct) ? toNumber(v.body_fat_pct) : null;
    const muscle = v.muscle_pct.trim() !== "" && inRange(v.muscle_pct, RANGES.muscle_pct) ? toNumber(v.muscle_pct) : null;
    if (fat !== null && muscle !== null && fat + muscle > 100) {
      ctx.addIssue({ code: "custom", path: ["muscle_pct"], message: "La suma de % grasa y % músculo no puede superar 100" });
    }
  });

export type MeasurementFormValues = z.infer<typeof measurementSchema>;

export const OPTIONAL_FIELDS = [
  "body_fat_pct", "muscle_pct", "chest_cm", "waist_cm", "hips_cm", "arms_cm", "thighs_cm", "calves_cm",
] as const;

export const emptyMeasurementForm: MeasurementFormValues = {
  recorded_on: "", weight_kg: "", height: "", height_unit: "cm",
  body_fat_pct: "", muscle_pct: "", chest_cm: "", waist_cm: "", hips_cm: "", arms_cm: "",
  thighs_cm: "", calves_cm: "", notes: "",
};

/** Convierte la estatura escrita (cm o m) a centímetros, como la espera el backend. */
export function heightToCm(value: string, unit: "cm" | "m"): string {
  const n = toNumber(value);
  return String(unit === "m" ? Math.round(n * 100 * 100) / 100 : n);
}

/**
 * Cambia la unidad convirtiendo el valor ya escrito (175 cm ⇄ 1.75 m).
 * Al pasar a metros se redondea al centímetro (la entrada admite 2 decimales).
 */
export function convertHeight(value: string, from: "cm" | "m", to: "cm" | "m"): string {
  if (from === to || !isDecimal(value)) return value;
  const n = toNumber(value);
  return String(to === "m" ? Math.round(n) / 100 : Math.round(n * 100 * 100) / 100);
}

export function measurementToForm(m: Measurement): MeasurementFormValues {
  return {
    recorded_on: "",
    weight_kg: trimDecimal(m.weight_kg),
    height: trimDecimal(m.height_cm),
    height_unit: "cm",
    body_fat_pct: trimDecimal(m.body_fat_pct),
    muscle_pct: trimDecimal(m.muscle_pct),
    chest_cm: trimDecimal(m.chest_cm),
    waist_cm: trimDecimal(m.waist_cm),
    hips_cm: trimDecimal(m.hips_cm),
    arms_cm: trimDecimal(m.arms_cm),
    thighs_cm: trimDecimal(m.thighs_cm),
    calves_cm: trimDecimal(m.calves_cm),
    notes: m.notes ?? "",
  };
}

const optionalValue = (v: string) => (v.trim() === "" ? undefined : normalizeDecimal(v));
const nullableValue = (v: string) => (v.trim() === "" ? null : normalizeDecimal(v));

export function toCreatePayload(v: MeasurementFormValues): MeasurementCreatePayload {
  const payload: MeasurementCreatePayload = {
    weight_kg: normalizeDecimal(v.weight_kg),
    height_cm: heightToCm(v.height, v.height_unit),
  };
  for (const f of OPTIONAL_FIELDS) {
    const value = optionalValue(v[f]);
    if (value !== undefined) payload[f] = value;
  }
  if (v.notes.trim()) payload.notes = v.notes.trim();
  // Hoy (o vacío) → el servidor usa la hora actual. Otra fecha → mediodía local, enviado en UTC.
  if (v.recorded_on && v.recorded_on !== todayISO()) {
    payload.recorded_at = new Date(`${v.recorded_on}T12:00:00`).toISOString();
  }
  return payload;
}

/** En edición, un campo opcional vacío se envía como null para borrarlo. */
export function toUpdatePayload(v: MeasurementFormValues): MeasurementUpdatePayload {
  return {
    weight_kg: normalizeDecimal(v.weight_kg),
    height_cm: heightToCm(v.height, v.height_unit),
    body_fat_pct: nullableValue(v.body_fat_pct),
    muscle_pct: nullableValue(v.muscle_pct),
    chest_cm: nullableValue(v.chest_cm),
    waist_cm: nullableValue(v.waist_cm),
    hips_cm: nullableValue(v.hips_cm),
    arms_cm: nullableValue(v.arms_cm),
    thighs_cm: nullableValue(v.thighs_cm),
    calves_cm: nullableValue(v.calves_cm),
    notes: v.notes.trim() || null,
  };
}
