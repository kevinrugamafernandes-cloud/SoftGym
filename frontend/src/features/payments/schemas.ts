import { z } from "zod";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";
import { addDaysISO, isISODate, todayISO } from "@/lib/dates";
import { REFERENCE_REQUIRED_METHODS, PAYMENT_METHOD_LABELS } from "@/lib/labels";
import type { MembershipSummary, PaymentCreatePayload, PaymentMethod } from "@/types";

export const PAYMENT_METHODS = Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[];

/** Límite de Numeric(10, 2) en la base de datos. */
const MAX_AMOUNT = 99_999_999.99;

export const paymentFormSchema = z
  .object({
    member_id: z.string().min(1, "Seleccione un socio"),
    plan_id: z.string().min(1, "Seleccione un plan"),
    amount: z
      .string()
      .trim()
      .min(1, "Indique el monto cobrado")
      .refine((v) => isDecimal(v, 2), "Monto inválido (use números, con hasta 2 decimales)")
      .refine((v) => Number(normalizeDecimal(v)) <= MAX_AMOUNT, "El monto es demasiado alto"),
    method: z.enum(["efectivo", "tarjeta", "transferencia", "sinpe", "otro"], {
      errorMap: () => ({ message: "Seleccione el método de pago" }),
    }),
    payment_date: z
      .string()
      .min(1, "Indique la fecha del pago")
      .refine(isISODate, "Fecha inválida")
      .refine((v) => v <= todayISO(), "La fecha del pago no puede ser futura"),
    reference: z.string().trim().max(100, "Máximo 100 caracteres"),
    notes: z.string().trim().max(1000, "Máximo 1000 caracteres"),
  })
  .superRefine((values, ctx) => {
    if (REFERENCE_REQUIRED_METHODS.has(values.method) && !values.reference) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["reference"],
        message: `Para ${PAYMENT_METHOD_LABELS[values.method]} indique el número de referencia o comprobante`,
      });
    }
  });

export type PaymentFormValues = z.infer<typeof paymentFormSchema>;

export const PAYMENT_FORM_FIELDS = ["member_id", "plan_id", "amount", "method", "payment_date", "reference", "notes"] as const;

export const emptyPaymentForm = (memberId = ""): PaymentFormValues => ({
  member_id: memberId,
  plan_id: "",
  amount: "",
  method: "efectivo",
  payment_date: todayISO(),
  reference: "",
  notes: "",
});

export function toPaymentPayload(values: PaymentFormValues, confirmDuplicate: boolean): PaymentCreatePayload {
  return {
    member_id: values.member_id,
    plan_id: values.plan_id,
    amount: normalizeDecimal(values.amount),
    method: values.method,
    payment_date: values.payment_date,
    reference: values.reference || null,
    notes: values.notes || null,
    confirm_duplicate: confirmDuplicate,
  };
}

/**
 * Vista previa del periodo, con la MISMA regla del backend: si el socio aún tiene membresía
 * vigente a la fecha del pago, el nuevo periodo empieza el día siguiente a su vencimiento
 * (renovar antes no hace perder días); si no, empieza en la fecha del pago.
 * Es solo informativa: el periodo definitivo lo devuelve el servidor.
 */
export function previewPeriod(
  membership: MembershipSummary | null | undefined,
  paymentDate: string,
  durationDays: number
): { start: string; end: string; extendsCurrent: boolean } | null {
  if (!isISODate(paymentDate) || durationDays < 1) return null;
  const extendsCurrent = Boolean(membership && membership.end_date >= paymentDate);
  const start = extendsCurrent && membership ? addDaysISO(membership.end_date, 1) : paymentDate;
  return { start, end: addDaysISO(start, durationDays - 1), extendsCurrent };
}
