import type { Gender, MemberStatus, MovementKind, PaymentMethod, UserRole } from "@/types";

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrador",
  receptionist: "Recepcionista",
  trainer: "Entrenador",
  member: "Socio",
};

export const MEMBER_STATUS_LABELS: Record<MemberStatus, string> = {
  activo: "Activo",
  por_vencer: "Por vencer",
  moroso: "Moroso",
  inactivo: "Inactivo",
};

export const GENDER_LABELS: Record<Gender, string> = {
  masculino: "Masculino",
  femenino: "Femenino",
  otro: "Otro",
  prefiero_no_decir: "Prefiero no decir",
};

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  efectivo: "Efectivo",
  tarjeta: "Tarjeta",
  transferencia: "Transferencia",
  sinpe: "SINPE Móvil",
  otro: "Otro",
};

/** Métodos que se concilian contra el banco: el backend exige el número de referencia. */
export const REFERENCE_REQUIRED_METHODS: ReadonlySet<PaymentMethod> = new Set<PaymentMethod>(["sinpe", "transferencia"]);

export const MOVEMENT_KIND_LABELS: Record<MovementKind, string> = {
  inicial: "Inventario inicial",
  entrada: "Entrada",
  venta: "Venta",
  anulacion_venta: "Anulación de venta",
  ajuste: "Ajuste",
};
