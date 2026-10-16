import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Pagination } from "@/components/common/Pagination";
import { StatTile } from "@/components/common/StatTile";
import { usePermissions } from "@/features/auth";
import { PaymentFormDialog } from "@/features/payments/components/PaymentFormDialog";
import { PaymentsNav } from "@/features/payments/components/PaymentsNav";
import { PaymentsTable } from "@/features/payments/components/PaymentsTable";
import { VoidPaymentDialog } from "@/features/payments/components/VoidPaymentDialog";
import { PAYMENT_METHODS } from "@/features/payments/schemas";
import { useGymCurrency, usePayments } from "@/hooks/usePayments";
import { addDaysISO, isISODate, startOfMonthISO, todayISO } from "@/lib/dates";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import type { Payment, PaymentFilters, PaymentMethod } from "@/types";

const PAGE_SIZE = 15;

type Preset = "hoy" | "7d" | "mes" | "todo";
const PRESETS: { id: Preset; label: string; range: () => [string, string] }[] = [
  { id: "hoy", label: "Hoy", range: () => [todayISO(), todayISO()] },
  { id: "7d", label: "Últimos 7 días", range: () => [addDaysISO(todayISO(), -6), todayISO()] },
  { id: "mes", label: "Este mes", range: () => [startOfMonthISO(), todayISO()] },
  { id: "todo", label: "Todo", range: () => ["", ""] },
];

export function PaymentsPage() {
  const { can } = usePermissions();
  const currency = useGymCurrency();
  const [params, setParams] = useSearchParams();

  // Filtros en la URL: recargar o volver con "atrás" los conserva. Por defecto: hoy.
  const hasRange = params.has("desde") || params.has("hasta");
  const dateFrom = hasRange ? params.get("desde") ?? "" : todayISO();
  const dateTo = hasRange ? params.get("hasta") ?? "" : todayISO();
  const rawMethod = params.get("metodo") ?? "";
  const method = (PAYMENT_METHODS.includes(rawMethod as PaymentMethod) ? rawMethod : "") as PaymentMethod | "";
  const includeVoided = params.get("anulados") !== "no";
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);
  const memberId = params.get("socio") ?? "";

  const update = useCallback(
    (next: Record<string, string | number | undefined>) => {
      setParams((prev) => {
        const p = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(next)) {
          if (v === undefined || (k === "pagina" && v === 1) || (k === "socio" && v === "")) p.delete(k);
          else p.set(k, String(v));
        }
        return p;
      }, { replace: true });
    },
    [setParams]
  );

  const filters: PaymentFilters = {
    date_from: isISODate(dateFrom) ? dateFrom : "",
    date_to: isISODate(dateTo) ? dateTo : "",
    method, member_id: memberId, include_voided: includeVoided, page, size: PAGE_SIZE,
  };
  const rangeError = filters.date_from && filters.date_to && filters.date_from > filters.date_to
    ? "La fecha inicial es posterior a la final." : null;
  const payments = usePayments(filters, { enabled: !rangeError });
  const data = payments.data;

  useEffect(() => {
    if (data && data.pages > 0 && page > data.pages) update({ pagina: data.pages });
  }, [data, page, update]);

  const activePreset = useMemo(
    () => PRESETS.find((p) => { const [a, b] = p.range(); return a === filters.date_from && b === filters.date_to; })?.id,
    [filters.date_from, filters.date_to]
  );

  const [charging, setCharging] = useState(false);

  // Acceso directo del panel principal: /payments?cobrar=1 abre el cobro.
  useEffect(() => {
    if (params.get("cobrar") === "1" && can("payments.create")) {
      setCharging(true);
      setParams((prev) => { const p = new URLSearchParams(prev); p.delete("cobrar"); return p; }, { replace: true });
    }
  }, [params, setParams, can]);
  const [voidTarget, setVoidTarget] = useState<Payment | null>(null);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Pagos y caja</h2>
          <p className="mt-1 text-sm text-muted-foreground">Registre cobros de membresía, consulte el historial y emita comprobantes.</p>
        </div>
        {can("payments.create") && (
          <Button variant="gold" onClick={() => setCharging(true)} className="shrink-0">
            <Plus className="mr-2 h-4 w-4" aria-hidden /> Registrar cobro
          </Button>
        )}
      </div>

      <PaymentsNav />

      <Card>
        <CardContent className="space-y-5 p-4 sm:p-6">
          {/* ── Filtros ── */}
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Rango rápido">
              {PRESETS.map((p) => (
                <Button key={p.id} type="button" size="sm" variant={activePreset === p.id ? "gold" : "outline"}
                  onClick={() => { const [a, b] = p.range(); update({ desde: a, hasta: b, pagina: 1 }); }}>
                  {p.label}
                </Button>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1.5">
                <Label htmlFor="f-desde">Desde</Label>
                <Input id="f-desde" type="date" max={todayISO()} value={filters.date_from} className="[color-scheme:dark]"
                  onChange={(e) => update({ desde: e.target.value, hasta: filters.date_to, pagina: 1 })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="f-hasta">Hasta</Label>
                <Input id="f-hasta" type="date" max={todayISO()} value={filters.date_to} className="[color-scheme:dark]"
                  onChange={(e) => update({ desde: filters.date_from, hasta: e.target.value, pagina: 1 })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="f-metodo">Método</Label>
                <Select id="f-metodo" value={method} onChange={(e) => update({ metodo: e.target.value || undefined, pagina: 1 })}>
                  <option value="">Todos</option>
                  {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>)}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="f-anulados">Anulados</Label>
                <Select id="f-anulados" value={includeVoided ? "si" : "no"}
                  onChange={(e) => update({ anulados: e.target.value === "no" ? "no" : undefined, pagina: 1 })}>
                  <option value="si">Mostrar anulados</option>
                  <option value="no">Ocultar anulados</option>
                </Select>
              </div>
            </div>
            {memberId && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-gold">
                  Socio: {data?.items[0]?.member.full_name ?? "seleccionado"}
                </span>
                <Button type="button" variant="ghost" size="sm" onClick={() => update({ socio: undefined, pagina: 1 })}>
                  Quitar filtro
                </Button>
              </div>
            )}
            {rangeError && <p className="text-sm text-destructive" role="alert">{rangeError}</p>}
          </div>

          {/* ── Totales del filtro (no solo de la página) ── */}
          {data && !rangeError && (
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile label="Cobrado" value={formatMoney(data.totals.active_total, currency)}
                hint={`${data.totals.active_count} ${data.totals.active_count === 1 ? "cobro" : "cobros"}`} tone="gold" />
              <StatTile label="Anulado" value={formatMoney(data.totals.voided_total, currency)}
                hint={`${data.totals.voided_count} ${data.totals.voided_count === 1 ? "pago" : "pagos"}`}
                tone={data.totals.voided_count > 0 ? "danger" : "muted"} />
              <StatTile label="Ticket promedio"
                value={data.totals.active_count ? formatMoney(Number(data.totals.active_total) / data.totals.active_count, currency) : "—"}
                hint="Sin contar anulados" tone="muted" />
            </div>
          )}

          <PaymentsTable
            payments={rangeError ? [] : data?.items}
            currency={currency}
            loading={payments.isLoading}
            error={payments.error}
            onRetry={() => void payments.refetch()}
            canVoid={can("payments.void")}
            onVoid={setVoidTarget}
            emptyTitle="Sin pagos en este rango"
            emptyDescription="Cambie las fechas o el método para ver otros cobros."
            emptyAction={can("payments.create") ? (
              <Button variant="gold" onClick={() => setCharging(true)}><Plus className="mr-2 h-4 w-4" aria-hidden /> Registrar cobro</Button>
            ) : undefined}
          />

          {data && !rangeError && (
            <Pagination page={data.page} pages={data.pages} total={data.total} size={data.size}
              onPageChange={(p) => update({ pagina: p })} disabled={payments.isFetching} />
          )}
        </CardContent>
      </Card>

      {charging && <PaymentFormDialog open currency={currency} onOpenChange={(o) => !o && setCharging(false)} />}
      <VoidPaymentDialog payment={voidTarget} currency={currency} onOpenChange={(o) => !o && setVoidTarget(null)} />
    </div>
  );
}
