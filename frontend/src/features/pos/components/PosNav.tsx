import { NavLink } from "react-router-dom";
import { usePermissions } from "@/features/auth";
import { cn } from "@/utils";

/** Pestañas de la tienda: Vender, Ventas e Inventario. */
export function PosNav() {
  const { can } = usePermissions();
  const tabs = [
    { to: "/tienda", label: "Vender", end: true, show: can("pos.sell") },
    { to: "/tienda/ventas", label: "Ventas", end: false, show: can("sales.view") },
    { to: "/tienda/inventario", label: "Inventario", end: false, show: can("products.view") },
  ].filter((t) => t.show);
  return (
    <nav aria-label="Secciones de la tienda" className="flex gap-1 border-b border-border print:hidden">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} end={t.end}
          className={({ isActive }) => cn(
            "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
            isActive ? "border-gold font-medium text-gold" : "border-transparent text-muted-foreground hover:text-foreground"
          )}>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
