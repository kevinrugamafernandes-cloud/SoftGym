import { Navigate, Outlet } from "react-router-dom";
import { hasPermission, useAuth, type Permission } from "@/features/auth";
import type { UserRole } from "@/types";

// ── Loading spinner used during session restore ───────────────────────────────

function SessionLoader() {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-gold border-t-transparent" />
        <span className="text-sm text-muted-foreground">Cargando sesión…</span>
      </div>
    </div>
  );
}

// ── Protected route — redirects to /login if not authenticated ────────────────

interface ProtectedRouteProps {
  /** If provided, only users with this role can access the route. */
  requiredRole?: UserRole;
  /** If provided, the user's role must grant this permission (ver features/auth/permissions.ts). */
  permission?: Permission;
}

export function ProtectedRoute({ requiredRole, permission }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) return <SessionLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to="/dashboard" replace />;
  }
  if (permission && !hasPermission(user?.role, permission)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}

// ── Public route — redirects to /dashboard if already logged in ───────────────

export function PublicRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <SessionLoader />;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return <Outlet />;
}
