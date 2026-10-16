import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowRight, BarChart3, CreditCard, Lock, MessageCircle, Package, ShoppingBag, TrendingUp, UserPlus,
  Users, Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth, usePermissions } from "@/features/auth";
import { NoCashSessionAlert } from "@/features/cash/components/CashSessionIndicator";
import { useDashboard } from "@/hooks/useAdmin";
import { formatMoney } from "@/lib/money";
import { cn, formatDate } from "@/utils";

type Tone = "gold" | "success" | "warning" | "danger" | "muted";
const TONES: Record<Tone, string> = {
  gold: "text-gold bg-gold/10",
  success: "text-success bg-success/10",
  warning: "text-warning bg-warning/10",
  danger: "text-destructive bg-destructive/10",
  muted: "text-muted-foreground bg-muted",
};

function Kpi({ title, value, hint, icon: Icon, tone = "muted", to }: {
  title: string; value: string; hint?: string; icon: React.ElementType; tone?: Tone; to?: string;
}) {
  const body = (
    <CardContent className="flex items-center justify-between gap-3 p-5">
      <div className="min-w-0">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="mt-1 truncate text-2xl font-bold tabular-nums text-foreground">{value}</p>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-lg", TONES[tone])}>
        <Icon className="h-5 w-5" aria-hidden />
      </div>
    </CardContent>
  );
  return to ? (
    <Link to={to} className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <Card className="h-full transition-colors hover:border-gold/40">{body}</Card>
    </Link>
  ) : <Card className="h-full">{body}</Card>;
}

function Shortcut({ to, icon: Icon, label, hint }: { to: string; icon: React.ElementType; label: string; hint: string }) {
  return (
    <Link to={to}
      className="group flex items-center gap-3 rounded-lg border border-border bg-input/30 p-4 transition-colors hover:border-gold/50 hover:bg-gold/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-gold/10 text-gold">
        <Icon className="h-5 w-5" aria-hidden />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="truncate text-xs text-muted-foreground">{hint}</p>
      </div>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-gold" aria-hidden />
    </Link>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const { can } = usePermissions();
  const frontDesk = can("payments.view");
  const dash = useDashboard();
  const d = dash.data;
  const m = (v: string | number) => formatMoney(v, d?.currency ?? "CRC");
  const firstName = user?.full_name.split(" ")[0] ?? "";

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Hola, {firstName}</h2>
        <p className="mt-1 text-sm text-muted-foreground first-letter:uppercase">
          {formatDate(d?.date ?? new Date().toISOString().slice(0, 10), { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
        </p>
      </div>

      {frontDesk && d && d.my_session_open === false && <NoCashSessionAlert action="cobrar y vender hoy" />}

      {frontDesk && (
        dash.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>
        ) : d ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi title="Ingresos de hoy" value={m(d.today_total)} icon={Wallet} tone="gold" to="/payments/caja"
              hint={`Membresías ${m(d.today_memberships)} · Tienda ${m(d.today_store)}`} />
            <Kpi title="Ingresos del mes" value={m(d.month_total)} icon={TrendingUp} tone="success"
              to={can("reports.view") ? "/reports" : undefined} hint={`IVA incluido ${m(d.month_tax)}`} />
            <Kpi title="Socios activos" value={String(d.members_active + d.members_expiring)} icon={Users} tone="muted" to="/members"
              hint={`${d.members_expiring} por vencer · ${d.members_new_month} nuevos este mes`} />
            <Kpi title="Morosos" value={String(d.members_overdue)} icon={AlertTriangle}
              tone={d.members_overdue > 0 ? "danger" : "muted"} to="/cobranza" hint="Recordar por WhatsApp →" />
          </div>
        ) : null
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3"><CardTitle className="text-base">Accesos directos</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {can("members.create") && <Shortcut to="/members?nuevo=1" icon={UserPlus} label="Inscribir socio" hint="Datos + plan + cobro en un paso" />}
            {can("payments.create") && <Shortcut to="/payments?cobrar=1" icon={CreditCard} label="Cobrar o renovar" hint="Pase de día, quincena o mensualidad" />}
            {can("pos.sell") && <Shortcut to="/tienda" icon={ShoppingBag} label="Vender en tienda" hint="Bebidas, suplementos y snacks" />}
            {can("collections.view") && <Shortcut to="/cobranza" icon={MessageCircle} label="Morosos" hint="Recordatorios por WhatsApp" />}
            {can("cash.view") && <Shortcut to="/payments/caja" icon={Wallet} label="Caja del día" hint="Turnos, arqueos y cierre" />}
            {can("reports.view") && <Shortcut to="/reports" icon={BarChart3} label="Reportes y cierre mensual" hint="Libro de ventas e IVA para el contador" />}
            {!frontDesk && <Shortcut to="/members" icon={Users} label="Socios" hint="Consulta y ficha física" />}
          </CardContent>
        </Card>

        {frontDesk && d && (
          <Card>
            <CardHeader className="pb-3"><CardTitle className="text-base">Pendientes</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {d.low_stock_count > 0 && (
                <Link to="/tienda/inventario" className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 hover:bg-warning/15">
                  <Package className="h-4 w-4 shrink-0 text-warning" aria-hidden />
                  {d.low_stock_count} {d.low_stock_count === 1 ? "producto con" : "productos con"} stock bajo
                </Link>
              )}
              {d.members_expiring > 0 && (
                <Link to="/cobranza?estado=por_vencer" className="flex items-center gap-2 rounded-md border border-border bg-input/30 p-3 hover:border-gold/40">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
                  {d.members_expiring} {d.members_expiring === 1 ? "membresía vence" : "membresías vencen"} pronto
                </Link>
              )}
              {d.members_inactive > 0 && (
                <Link to="/members?estado=inactivo" className="flex items-center gap-2 rounded-md border border-border bg-input/30 p-3 hover:border-gold/40">
                  <Users className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  {d.members_inactive} {d.members_inactive === 1 ? "socio inactivo" : "socios inactivos"} (sin membresía vigente)
                </Link>
              )}
              <div className="space-y-2 border-t border-border pt-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Cajas abiertas</p>
                {d.open_sessions.length === 0 ? (
                  <p className="flex items-center gap-2 text-muted-foreground"><Lock className="h-4 w-4" aria-hidden /> Ninguna</p>
                ) : d.open_sessions.map((s) => (
                  <div key={s.cashier_name + s.opened_at} className="flex justify-between gap-2">
                    <span className="truncate">{s.cashier_name} <span className="text-xs text-muted-foreground">desde {new Date(s.opened_at).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" })}</span></span>
                    <span className="tabular-nums text-muted-foreground">{m(s.expected_cash)}</span>
                  </div>
                ))}
              </div>
              {d.low_stock_count === 0 && d.members_expiring === 0 && d.members_inactive === 0 && (
                <p className="text-muted-foreground">Todo al día. 👌</p>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {dash.isError && (
        <div className="flex items-center gap-3 text-sm text-destructive">
          No se pudieron cargar las métricas. <Button variant="outline" size="sm" onClick={() => void dash.refetch()}>Reintentar</Button>
        </div>
      )}
    </div>
  );
}
