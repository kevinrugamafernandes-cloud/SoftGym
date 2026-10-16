import { NavLink } from "react-router-dom";
import { usePermissions } from "@/features/auth";
import { cn } from "@/utils";

/** Pestañas del módulo: Cobros (historial) y Caja del día. */
export function PaymentsNav() {
  const { can } = usePermissions();
  const tabs = [
    { to: "/payments", label: "Cobros", end: true, show: can("payments.view") },
    { to: "/payments/caja", label: "Caja del día", end: false, show: can("cash.view") },
  ].filter((t) => t.show);

  return (
    <nav aria-label="Secciones de pagos" className="flex gap-1 border-b border-border">
      {tabs.map((t) => (
        <NavLink
          key={t.to} to={t.to} end={t.end}
          className={({ isActive }) =>
            cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              isActive ? "border-gold font-medium text-gold" : "border-transparent text-muted-foreground hover:text-foreground"
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
