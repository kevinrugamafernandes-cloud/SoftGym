import type { CashSessionFilters, MemberFilters, PaymentFilters, ProductFilters, SaleFilters } from "@/types";

/** Claves de caché de React Query, centralizadas para invalidar sin errores de tipeo. */
export const queryKeys = {
  members: {
    all: ["members"] as const,
    list: (filters: MemberFilters) => ["members", "list", filters] as const,
    detail: (id: string) => ["members", "detail", id] as const,
    cedula: (identification: string) => ["members", "cedula", identification] as const,
  },
  plans: {
    all: ["plans"] as const,
    list: (activeOnly: boolean) => ["plans", "list", { activeOnly }] as const,
    detail: (id: string) => ["plans", "detail", id] as const,
  },
  measurements: {
    all: ["measurements"] as const,
    list: (memberId: string, limit: number) => ["measurements", memberId, "list", { limit }] as const,
    forMember: (memberId: string) => ["measurements", memberId] as const,
  },
  payments: {
    all: ["payments"] as const,
    list: (filters: PaymentFilters) => ["payments", "list", filters] as const,
    detail: (id: string) => ["payments", "detail", id] as const,
    cash: (day: string) => ["payments", "cash", day] as const,
  },
  memberships: {
    forMember: (memberId: string) => ["memberships", memberId] as const,
  },
  cashSessions: {
    all: ["cash-sessions"] as const,
    current: ["cash-sessions", "current"] as const,
    list: (f: CashSessionFilters) => ["cash-sessions", "list", f] as const,
    detail: (id: string) => ["cash-sessions", "detail", id] as const,
  },
  products: {
    all: ["products"] as const,
    list: (f: ProductFilters) => ["products", "list", f] as const,
    categories: ["products", "categories"] as const,
    movements: (id: string, page: number) => ["products", "movements", id, page] as const,
  },
  sales: {
    all: ["sales"] as const,
    list: (f: SaleFilters) => ["sales", "list", f] as const,
  },
  settings: ["settings"] as const,
  dashboard: ["dashboard"] as const,
  collections: {
    all: ["collections"] as const,
    list: (f: { state: string; search: string; page: number; size: number }) => ["collections", "list", f] as const,
  },
  reports: {
    all: ["reports"] as const,
    salesBook: (from: string, to: string) => ["reports", "sales-book", from, to] as const,
    monthly: (year: number, month: number) => ["reports", "monthly", year, month] as const,
    closes: ["reports", "closes"] as const,
  },
};
