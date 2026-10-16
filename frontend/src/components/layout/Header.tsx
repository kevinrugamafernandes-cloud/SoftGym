import { Bell, LogOut, User } from "lucide-react";
import { useAuth } from "@/features/auth";
import { CashSessionIndicator } from "@/features/cash/components/CashSessionIndicator";
import { Button } from "@/components/ui/button";
import { ROLE_LABELS } from "@/lib/labels";
import { getInitials } from "@/utils";
import { cn } from "@/utils";

interface HeaderProps {
  pageTitle: string;
}

export function Header({ pageTitle }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-6">
      <h1 className="text-base font-semibold text-foreground">{pageTitle}</h1>

      <div className="flex items-center gap-3">
        {/* Estado de la caja del usuario (solo roles que cobran) */}
        <CashSessionIndicator />

        {/* Notification bell (placeholder for Phase 2+) */}
        <Button
          variant="ghost"
          size="icon"
          className="relative text-muted-foreground hover:text-foreground"
          aria-label="Notificaciones"
        >
          <Bell className="h-4 w-4" />
        </Button>

        {/* User avatar + role badge */}
        <div className="flex items-center gap-2 border-l border-border pl-3">
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold",
              "bg-gold text-background"
            )}
            aria-label="Avatar del usuario"
          >
            {user ? getInitials(user.full_name) : <User className="h-4 w-4" />}
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-medium leading-none text-foreground">
              {user?.full_name}
            </p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {user ? ROLE_LABELS[user.role] : ""}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground"
            onClick={logout}
            aria-label="Cerrar sesión"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
