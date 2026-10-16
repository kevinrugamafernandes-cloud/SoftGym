import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Printer, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { Pagination } from "@/components/common/Pagination";
import { StatTile } from "@/components/common/StatTile";
import { useAuth, usePermissions } from "@/features/auth";
import { CashSessionsCard } from "@/features/cash/components/CashSessionsCard";
import { PaymentsNav } from "@/features/payments/components/PaymentsNav";
import { PaymentsTable } from "@/features/payments/components/PaymentsTable";
import { VoidPaymentDialog } from "@/features/payments/components/VoidPaymentDialog";
import { useCashSummary, usePayments } from "@/hooks/usePayments";
import { getErrorMessage } from "@/lib/axios";
import { addDaysISO, isISODate, todayISO } from "@/lib/dates";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { formatDate } from "@/utils";
import type { Payment } from "@/types";

const PAGE_SIZE = 20;

export function CashPage() {
  const { user } = useAuth();
  const { can } = usePermissions();
  const [params, setParams] = useSearchParams();
  const today = todayISO();
  const raw = params.get("fecha") ?? today;
  const day = isISODate(raw) && raw <= today ? raw : today;
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);
  const setDay = (d: string) => setParams((prev) => {
    const p = new URLSearchParams(prev);
    if (d === today) p.delete("fecha"); else p.set("fecha", d);
    p.delete("pagina");
    return p;
  }, { replace: true });

  const summary = useCashSummary(day);
  const payments = usePayments({
    date_from: day, date_to: day, method: "", member_id: "", include_voided: true, page, size: PAGE_SIZE,
  });
  const currency = summary.data?.currency ?? "CRC";
  const [voidTarget, setVoidTarget] = useState<Payment | null>(null);

  const cashExpected = Number(summary.data?.by_method.find((m) => m.method === "efectivo")?.total ?? 0);

  const s = summary.data;
  const total = s ? Number(s.total) : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between print:hidden">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Pagos y caja</h2>
          <p className="mt-1 text-sm text-muted-foreground">Cierre diario: membresías y tienda de todas las cajas, por método, sin anulaciones.</p>
        </div>
        <Button variant="outline" onClick={() => window.print()} disabled={!s} className="shrink-0">
          <Printer className="mr-2 h-4 w-4" aria-hidden /> Imprimir cierre
        </Button>
      </div>

      <div className="print:hidden"><PaymentsNav /></div>

      {/* Encabezado que solo aparece en papel */}
      <div className="hidden print:block">
        <h1 className="text-lg font-bold">Cierre de caja · {formatDate(day, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</h1>
        <p className="text-sm">Impreso por {user?.full_name} el {new Date().toLocaleString("es-CR")}</p>
      </div>

      {/* ── Selector de día ── */}
      <div className="flex flex-wrap items-end gap-2 print:hidden">
        <Button variant="outline" size="icon" aria-label="Día anterior" onClick={() => setDay(addDaysISO(day, -1))}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="space-y-1.5">
          <Label htmlFor="cash-day" className="sr-only">Día</Label>
          <Input id="cash-day" type="date" max={today} value={day} className="w-44 [color-scheme:dark]"
            onChange={(e) => isISODate(e.target.value) && setDay(e.target.value)} />
        </div>
        <Button variant="outline" size="icon" aria-label="Día siguiente" disabled={day >= today} onClick={() => setDay(addDaysISO(day, 1))}>
          <ChevronRight className="h-4 w-4" />
        </Button>
        {day !== today && <Button variant="ghost" size="sm" onClick={() => setDay(today)}>Ir a hoy</Button>}
        <p className="ml-1 text-sm text-muted-foreground first-letter:uppercase">
          {formatDate(day, { weekday: "long", day: "numeric", month: "long" })}
          {day === today && <span> · se actualiza cada minuto</span>}
        </p>
      </div>

      {summary.isLoading && <div className="grid gap-3 sm:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>}
      {summary.isError && (
        <div className="space-y-3">
          <ErrorMessage title="No se pudo cargar la caja" message={getErrorMessage(summary.error)} />
          <Button variant="outline" size="sm" onClick={() => void summary.refetch()}>
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar
          </Button>
        </div>
      )}

      {s && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Total del día" value={formatMoney(s.total, currency)} tone="gold"
              hint={`${s.count} ${s.count === 1 ? "movimiento" : "movimientos"} · efectivo ${formatMoney(cashExpected, currency)}`} />
            <StatTile label="Membresías" value={formatMoney(s.payments_total, currency)}
              hint={`${s.payments_count} ${s.payments_count === 1 ? "cobro" : "cobros"}`} />
            <StatTile label="Tienda" value={formatMoney(s.sales_total, currency)}
              hint={`${s.sales_count} ${s.sales_count === 1 ? "venta" : "ventas"} · IVA ${formatMoney(s.sales_tax_total, currency)}`} />
            <StatTile label="Anulado" value={formatMoney(s.voided_total, currency)} tone={s.voided_count ? "danger" : "muted"}
              hint={`${s.voided_count} ${s.voided_count === 1 ? "anulación" : "anulaciones"} (no suman)`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-5">
            <Card className="lg:col-span-5">
              <CardHeader className="pb-2"><CardTitle className="text-base">Por método de pago</CardTitle></CardHeader>
              <CardContent>
                {s.by_method.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">No hay cobros registrados este día.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead>Método</TableHead>
                        <TableHead className="text-right">Cobros</TableHead>
                        <TableHead className="text-right">Total</TableHead>
                        <TableHead className="hidden w-1/3 sm:table-cell"><span className="sr-only">Proporción</span></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {s.by_method.map((m) => {
                        const pct = total > 0 ? (Number(m.total) / total) * 100 : 0;
                        return (
                          <TableRow key={m.method}>
                            <TableCell className="font-medium text-foreground">{PAYMENT_METHOD_LABELS[m.method]}</TableCell>
                            <TableCell className="text-right tabular-nums">{m.count}</TableCell>
                            <TableCell className="text-right font-medium tabular-nums text-foreground">{formatMoney(m.total, currency)}</TableCell>
                            <TableCell className="hidden sm:table-cell">
                              <div className="flex items-center gap-2">
                                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                                  <div className="h-full rounded-full bg-gold" style={{ width: `${pct}%` }} />
                                </div>
                                <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">{Math.round(pct)}%</span>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                      <TableRow className="hover:bg-transparent">
                        <TableCell className="font-semibold text-foreground">Total</TableCell>
                        <TableCell className="text-right font-semibold tabular-nums">{s.count}</TableCell>
                        <TableCell className="text-right font-semibold tabular-nums text-gold">{formatMoney(s.total, currency)}</TableCell>
                        <TableCell className="hidden sm:table-cell" />
                      </TableRow>
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

          </div>
        </>
      )}

      <div className="print:break-inside-avoid">
        <CashSessionsCard day={day} currency={currency} />
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">Cobros de membresía del día</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <PaymentsTable
            payments={payments.data?.items}
            currency={currency}
            loading={payments.isLoading}
            error={payments.error}
            onRetry={() => void payments.refetch()}
            canVoid={can("payments.void")}
            onVoid={setVoidTarget}
            emptyTitle="Sin cobros este día"
            emptyDescription="Los cobros registrados con esta fecha aparecerán aquí."
          />
          {payments.data && (
            <div className="print:hidden">
              <Pagination page={payments.data.page} pages={payments.data.pages} total={payments.data.total} size={payments.data.size}
                onPageChange={(p) => setParams((prev) => { const q = new URLSearchParams(prev); if (p === 1) q.delete("pagina"); else q.set("pagina", String(p)); return q; }, { replace: true })}
                disabled={payments.isFetching} />
            </div>
          )}
        </CardContent>
      </Card>

      <VoidPaymentDialog payment={voidTarget} currency={currency} onOpenChange={(o) => !o && setVoidTarget(null)} />
    </div>
  );
}
