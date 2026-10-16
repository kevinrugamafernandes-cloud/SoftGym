import type { PaginatedResponse } from "./index";
import type { MembershipSummary } from "./payments";

export type MemberStatus = "activo" | "por_vencer" | "moroso" | "inactivo";
export type Gender = "masculino" | "femenino" | "otro" | "prefiero_no_decir";

export interface Member {
  id: string;
  identification: string;
  first_name: string;
  last_name: string;
  full_name: string;
  birth_date: string | null;
  gender: Gender | null;
  phone: string | null;
  email: string | null;
  status: MemberStatus;
  joined_at: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  /** Membresía vigente (o la última) con días restantes; null si nunca ha pagado. */
  membership?: MembershipSummary | null;
}

export type MemberListResponse = PaginatedResponse<Member>;

export interface MemberFilters {
  search: string;
  status: MemberStatus | "";
  page: number;
  size: number;
}

export interface MemberCreatePayload {
  identification: string;
  first_name: string;
  last_name: string;
  birth_date?: string | null;
  gender?: Gender | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  joined_at?: string | null;
}

/** La cédula no es editable. Solo se puede alternar manualmente activo/inactivo. */
export interface MemberUpdatePayload {
  first_name?: string;
  last_name?: string;
  birth_date?: string | null;
  gender?: Gender | null;
  phone?: string | null;
  email?: string | null;
  notes?: string | null;
  status?: "activo" | "inactivo";
}

/** Respuesta de GET /members/cedula-lookup/{cedula} (Fácil Inscripción). */
export interface CedulaLookupResult {
  identification: string;
  full_name: string;
  first_name: string;
  last_name: string;
  birth_date: string | null;
  identification_type: string | null;
  source: "hacienda" | "local";
  /** Hacienda entrega un solo campo "nombre": la separación es aproximada. */
  needs_review: boolean;
  already_registered: boolean;
  existing_member_id: string | null;
  existing_member_deleted: boolean;
}
