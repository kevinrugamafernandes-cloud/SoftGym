import { z } from "zod";
import type { Member, MemberCreatePayload, MemberUpdatePayload } from "@/types";

// ── Utilidades ────────────────────────────────────────────────────────────────

/** "1-1234-5678" → "112345678" (igual que el backend). */
export const normalizeIdentification = (value: string): string =>
  value.replace(/[\s-]/g, "").toUpperCase();

/** La consulta automática solo aplica a cédulas/DIMEX numéricas de 9 a 12 dígitos. */
export const isLookupEligible = (value: string): boolean =>
  /^\d{9,12}$/.test(normalizeIdentification(value));

const pad = (n: number) => String(n).padStart(2, "0");

/** Fecha local de hoy como AAAA-MM-DD (no UTC: evita que "hoy" cambie de día de noche). */
export const todayISO = (): string => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

export const isRealDate = (value: string): boolean =>
  /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));

const optionalPastDate = (message: string) =>
  z.string().refine((v) => v === "" || (isRealDate(v) && v <= todayISO()), message);

const emailCheck = z.string().email();

// ── Esquema del formulario (todos los campos son texto; "" = vacío) ───────────

const base = z.object({
  first_name: z.string().trim().min(1, "El nombre es obligatorio").max(100, "Máximo 100 caracteres"),
  last_name: z.string().trim().min(1, "Los apellidos son obligatorios").max(100, "Máximo 100 caracteres"),
  birth_date: optionalPastDate("Ingrese una fecha de nacimiento válida (no puede ser futura)"),
  gender: z.enum(["", "masculino", "femenino", "otro", "prefiero_no_decir"]),
  phone: z
    .string()
    .refine(
      (v) => v.trim() === "" || /^\+?\d{7,15}$/.test(v.replace(/[\s\-()]/g, "")),
      "Teléfono inválido: use de 7 a 15 dígitos"
    ),
  email: z
    .string()
    .trim()
    .refine((v) => v === "" || emailCheck.safeParse(v).success, "Correo electrónico inválido"),
  notes: z.string().max(1000, "Máximo 1000 caracteres"),
  joined_at: optionalPastDate("Ingrese una fecha de ingreso válida (no puede ser futura)"),
  status: z.enum(["activo", "inactivo"]),
});

export const memberCreateSchema = base.extend({
  identification: z
    .string()
    .trim()
    .min(1, "La identificación es obligatoria")
    .refine(
      (v) => /^[A-Z0-9]{5,20}$/.test(normalizeIdentification(v)),
      "Use de 5 a 20 letras o números (sin símbolos)"
    ),
});

/**
 * En edición la cédula y la fecha de ingreso no se modifican NI se muestran: no deben
 * validarse (un campo oculto que falla bloquearía el envío sin ningún aviso visible).
 */
export const memberEditSchema = base.extend({ identification: z.string(), joined_at: z.string() });

export type MemberFormValues = z.infer<typeof memberCreateSchema>;
export const MEMBER_FORM_FIELDS = [
  "identification", "first_name", "last_name", "birth_date", "gender",
  "phone", "email", "notes", "joined_at", "status",
] as const;

export const emptyMemberForm: MemberFormValues = {
  identification: "", first_name: "", last_name: "", birth_date: "", gender: "",
  phone: "", email: "", notes: "", joined_at: "", status: "activo",
};

export function memberToForm(member: Member): MemberFormValues {
  return {
    identification: member.identification,
    first_name: member.first_name,
    last_name: member.last_name,
    birth_date: member.birth_date ?? "",
    gender: member.gender ?? "",
    phone: member.phone ?? "",
    email: member.email ?? "",
    notes: member.notes ?? "",
    joined_at: member.joined_at,
    status: member.status === "inactivo" ? "inactivo" : "activo",
  };
}

/** `moroso` y `por_vencer` los calcula el sistema: solo activo/inactivo se editan a mano. */
export const isManualStatus = (status: Member["status"]): boolean =>
  status === "activo" || status === "inactivo";

export function toCreatePayload(v: MemberFormValues): MemberCreatePayload {
  return {
    identification: normalizeIdentification(v.identification),
    first_name: v.first_name.trim(),
    last_name: v.last_name.trim(),
    birth_date: v.birth_date || null,
    gender: v.gender || null,
    phone: v.phone.trim() || null,
    email: v.email.trim() || null,
    notes: v.notes.trim() || null,
    // Si se omite, el backend usa la fecha del SERVIDOR (UTC): pasadas las 6 p. m. en Costa Rica
    // sería "mañana". Se envía siempre la fecha local.
    joined_at: v.joined_at || todayISO(),
  };
}

export function toUpdatePayload(v: MemberFormValues, member: Member): MemberUpdatePayload {
  const statusChanged = isManualStatus(member.status) && v.status !== member.status;
  return {
    first_name: v.first_name.trim(),
    last_name: v.last_name.trim(),
    birth_date: v.birth_date || null,
    gender: v.gender || null,
    phone: v.phone.trim() || null,
    email: v.email.trim() || null,
    notes: v.notes.trim() || null,
    ...(statusChanged ? { status: v.status } : {}),
  };
}
