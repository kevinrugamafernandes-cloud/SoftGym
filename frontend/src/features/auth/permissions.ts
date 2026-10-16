import type { UserRole } from "@/types";

/**
 * Matriz de permisos de la interfaz. Refleja lo que el backend permite y aplica la
 * especificación funcional; el backend SIEMPRE valida de nuevo (403), esto solo decide
 * qué botones se muestran.
 *
 *   Administrador : todo (socios, baja/restauración, medidas completas, planes).
 *   Recepcionista : registrar, editar y consultar socios; consultar planes.
 *   Entrenador    : consultar socios y registrar/consultar medidas corporales.
 *   Socio         : sin acceso al panel administrativo.
 *
 *   Pagos y caja  : administrador y recepcionista cobran y ven la caja; solo el
 *                   administrador anula (el backend lo exige con AdminUser).
 *   Caja          : cada cajero abre y cierra SU turno; el administrador ve y cierra todos (cash.all).
 *   Morosos       : administrador y recepcionista (recordatorios por WhatsApp).
 *   Reportes y Configuración: solo administrador. Inscribir SIN cobro (socio inactivo), solo administrador.
 *   Tienda (POS)  : administrador y recepcionista venden y consultan; solo el administrador
 *                   gestiona el catálogo/inventario y anula ventas.
 *
 * NOTA: el backend también deja a la recepcionista consultar y registrar medidas.
 * Si se desea habilitarlo en la interfaz, basta con agregar "measurements.view" y
 * "measurements.create" a la lista de "receptionist" más abajo.
 */
export type Permission =
  | "members.view"
  | "members.create"
  | "members.edit"
  | "members.delete"
  | "members.restore"
  | "members.lookup"
  | "measurements.view"
  | "measurements.create"
  | "measurements.edit"
  | "measurements.delete"
  | "plans.view"
  | "plans.manage"
  | "payments.view"
  | "payments.create"
  | "payments.void"
  | "cash.view"
  | "cash.all"
  | "pos.sell"
  | "products.view"
  | "products.manage"
  | "sales.view"
  | "sales.void"
  | "collections.view"
  | "reports.view"
  | "settings.manage"
  | "members.create_without_payment";

const ALL: Permission[] = [
  "members.view", "members.create", "members.edit", "members.delete", "members.restore",
  "members.lookup", "measurements.view", "measurements.create", "measurements.edit",
  "measurements.delete", "plans.view", "plans.manage",
  "payments.view", "payments.create", "payments.void", "cash.view", "cash.all",
  "pos.sell", "products.view", "products.manage", "sales.view", "sales.void",
  "collections.view", "reports.view", "settings.manage", "members.create_without_payment",
];

const MATRIX: Record<UserRole, ReadonlySet<Permission>> = {
  admin: new Set(ALL),
  receptionist: new Set<Permission>([
    "members.view", "members.create", "members.edit", "members.lookup", "plans.view",
    "payments.view", "payments.create", "cash.view",
    "pos.sell", "products.view", "sales.view", "collections.view",
  ]),
  trainer: new Set<Permission>(["members.view", "measurements.view", "measurements.create"]),
  member: new Set<Permission>(),
};

export function hasPermission(role: UserRole | null | undefined, permission: Permission): boolean {
  return role ? MATRIX[role].has(permission) : false;
}
