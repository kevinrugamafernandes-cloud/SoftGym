import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  CreditCard,
  MessageCircle,
  BarChart3,
  Settings,
  ChevronLeft,
  Dumbbell,
  ShoppingBag,
} from "lucide-react";
import { cn } from "@/utils";
import { useAuth, usePermissions, type Permission } from "@/features/auth";
import type { UserRole } from "@/types";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  adminOnly?: boolean;
  /** Si se indica, solo estos roles ven el enlace. */
  roles?: UserRole[];
  /** Si se indica, el rol debe tener este permiso. */
  permission?: Permission;
}

const navItems: NavItem[] = [
  { label: "Dashboard",   href: "/dashboard",  icon: LayoutDashboard },
  { label: "Socios",      href: "/members",    icon: Users, permission: "members.view" },
  { label: "Pagos",       href: "/payments",   icon: CreditCard, permission: "payments.view" },
  { label: "Tienda",      href: "/tienda",     icon: ShoppingBag, permission: "pos.sell" },
  { label: "Morosos",     href: "/cobranza",   icon: MessageCircle, permission: "collections.view" },
  // Asistencia: oculta en esta versión (la ruta /attendance se habilitará en una fase futura).
  { label: "Reportes",    href: "/reports",    icon: BarChart3, permission: "reports.view" },
  { label: "Configuración",href: "/settings",  icon: Settings,  permission: "settings.manage" },
];

interface SidebarProps {
  collapsed: boolean;
  onCollapse: (v: boolean) => void;
}

export function Sidebar({ collapsed, onCollapse }: SidebarProps) {
  const { isAdmin, user } = useAuth();
  const { can } = usePermissions();
  const location = useLocation();

  const visible = navItems.filter(
    (item) =>
      (!item.adminOnly || isAdmin) &&
      (!item.roles || (user !== null && item.roles.includes(user.role))) &&
      (!item.permission || can(item.permission))
  );

  return (
    <aside
      className={cn(
        "relative flex flex-col bg-card border-r border-border transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center border-b border-border px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gold">
          <Dumbbell className="h-4 w-4 text-background" />
        </div>
        {!collapsed && (
          <div className="ml-3 overflow-hidden">
            <p className="text-sm font-semibold text-foreground leading-none">SoftGym</p>
            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">Lion Fitness Center</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
        {visible.map(({ label, href, icon: Icon }) => {
          const active = location.pathname.startsWith(href);
          return (
            <NavLink
              key={href}
              to={href}
              title={collapsed ? label : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-gold/10 text-gold font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => onCollapse(!collapsed)}
        className={cn(
          "absolute -right-3 top-20 z-10 flex h-6 w-6 items-center justify-center",
          "rounded-full border border-border bg-card text-muted-foreground",
          "hover:text-foreground transition-colors shadow-sm"
        )}
        aria-label={collapsed ? "Expandir barra lateral" : "Contraer barra lateral"}
      >
        <ChevronLeft
          className={cn("h-3 w-3 transition-transform", collapsed && "rotate-180")}
        />
      </button>
    </aside>
  );
}
