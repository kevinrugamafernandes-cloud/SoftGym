// ── Auth & Users ──────────────────────────────────────────────────────────────

export type UserRole = "admin" | "receptionist" | "trainer" | "member";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
}

// ── API responses ─────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  code?: string;
  errors?: { field: string; message: string }[];
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface PaginationParams {
  page?: number;
  size?: number;
  search?: string;
}

// ── Dominio (Fase 2) ──────────────────────────────────────────────────────────

export * from "./members";
export * from "./plans";
export * from "./measurements";
export * from "./payments";
export * from "./pos";
export * from "./admin";
