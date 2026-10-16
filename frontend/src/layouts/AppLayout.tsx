import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":  "Dashboard",
  "/members":    "Socios",
  "/payments":   "Pagos",
  "/tienda":     "Tienda",
  "/cobranza":   "Morosos",
  "/reports":    "Reportes",
  "/settings":   "Configuración",
};

const MOBILE_QUERY = "(max-width: 767px)";
const isMobile = () => typeof window.matchMedia === "function" && window.matchMedia(MOBILE_QUERY).matches;

export function AppLayout() {
  // En pantallas pequeñas la barra lateral arranca colapsada (si no, ocupa más de la mitad).
  const [sidebarCollapsed, setSidebarCollapsed] = useState(isMobile);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(MOBILE_QUERY);
    const onChange = (e: MediaQueryListEvent) => { if (e.matches) setSidebarCollapsed(true); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const location = useLocation();

  const pageTitle =
    Object.entries(PAGE_TITLES).find(([path]) =>
      location.pathname.startsWith(path)
    )?.[1] ?? "SoftGym";

  return (
    <div className="flex h-screen overflow-hidden bg-background print:block print:h-auto print:overflow-visible">
      {/* Sidebar */}
      <div className="contents print:hidden">
        <Sidebar
          collapsed={sidebarCollapsed}
          onCollapse={setSidebarCollapsed}
        />
      </div>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden print:block print:overflow-visible">
        <div className="print:hidden"><Header pageTitle={pageTitle} /></div>
        <main className="flex-1 overflow-y-auto p-3 sm:p-6 animate-fade-in print:overflow-visible print:p-0">
          {/* Suspense aquí: al cambiar de página el menú y el encabezado no parpadean mientras carga el módulo. */}
          <Suspense fallback={<div className="flex h-40 items-center justify-center" aria-busy="true" aria-label="Cargando"><div className="h-6 w-6 animate-spin rounded-full border-2 border-gold border-t-transparent" /></div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
