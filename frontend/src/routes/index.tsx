import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute, PublicRoute } from "./guards";

// Layouts
import { AppLayout } from "@/layouts/AppLayout";

// Páginas: se cargan bajo demanda (cada módulo en su propio archivo JS) para que la primera carga sea liviana.
const LoginPage = lazy(() => import("@/pages/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() => import("@/pages/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const MemberDetailPage = lazy(() => import("@/pages/members/MemberDetailPage").then((m) => ({ default: m.MemberDetailPage })));
const MembersPage = lazy(() => import("@/pages/members/MembersPage").then((m) => ({ default: m.MembersPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));
const CashPage = lazy(() => import("@/pages/payments/CashPage").then((m) => ({ default: m.CashPage })));
const PaymentsPage = lazy(() => import("@/pages/payments/PaymentsPage").then((m) => ({ default: m.PaymentsPage })));
const InventoryPage = lazy(() => import("@/pages/pos/InventoryPage").then((m) => ({ default: m.InventoryPage })));
const PosPage = lazy(() => import("@/pages/pos/PosPage").then((m) => ({ default: m.PosPage })));
const SalesPage = lazy(() => import("@/pages/pos/SalesPage").then((m) => ({ default: m.SalesPage })));
const CollectionsPage = lazy(() => import("@/pages/collections/CollectionsPage").then((m) => ({ default: m.CollectionsPage })));
const ReportsPage = lazy(() => import("@/pages/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const SettingsPage = lazy(() => import("@/pages/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));

function PageLoader() {
  return (
    <div className="flex h-40 items-center justify-center" aria-busy="true" aria-label="Cargando">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-gold border-t-transparent" />
    </div>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
    <Routes>
      {/* Public routes — redirect to dashboard if logged in */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Protected routes — redirect to login if not authenticated */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />

          {/* Socios: administrador, recepcionista y entrenador (el socio "member" no accede) */}
          <Route element={<ProtectedRoute permission="members.view" />}>
            <Route path="/members" element={<MembersPage />} />
            <Route path="/members/:memberId" element={<MemberDetailPage />} />
          </Route>

          {/* Pagos y caja: administrador y recepcionista (anular: solo administrador) */}
          <Route element={<ProtectedRoute permission="payments.view" />}>
            <Route path="/payments" element={<PaymentsPage />} />
          </Route>
          <Route element={<ProtectedRoute permission="cash.view" />}>
            <Route path="/payments/caja" element={<CashPage />} />
          </Route>

          {/* Tienda (POS): vender e historial (admin y recepcionista); catálogo: gestión solo admin */}
          <Route element={<ProtectedRoute permission="pos.sell" />}>
            <Route path="/tienda" element={<PosPage />} />
          </Route>
          <Route element={<ProtectedRoute permission="sales.view" />}>
            <Route path="/tienda/ventas" element={<SalesPage />} />
          </Route>
          <Route element={<ProtectedRoute permission="products.view" />}>
            <Route path="/tienda/inventario" element={<InventoryPage />} />
          </Route>

          {/* Morosos: administrador y recepcionista */}
          <Route element={<ProtectedRoute permission="collections.view" />}>
            <Route path="/cobranza" element={<CollectionsPage />} />
          </Route>

          {/* Contabilidad y configuración: solo administrador */}
          <Route element={<ProtectedRoute permission="reports.view" />}>
            <Route path="/reports" element={<ReportsPage />} />
          </Route>
          <Route element={<ProtectedRoute permission="settings.manage" />}>
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Asistencia: oculta en esta versión (se habilitará en una fase futura). */}
        </Route>
      </Route>

      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
    </Suspense>
  );
}
