import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Ban, Eye, Receipt, RefreshCw } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { Pagination } from "@/components/common/Pagination";
import { StatTile } from "@/components/common/StatTile";
import { usePermissions } from "@/features/auth";
import { PAYMENT_METHODS } from "@/features/payments/schemas";
import { PosNav } from "@/features/pos/components/PosNav";
import { SaleReceipt } from "@/features/pos/components/SaleReceipt";
import { VoidSaleDialog } from "@/features/pos/components/VoidSaleDialog";
import { useGymCurrency } from "@/hooks/usePayments";
import { useSales } from "@/hooks/useSales";
import { getErrorMessage } from "@/lib/axios";
import { addDaysISO, isISODate, startOfMonthISO, todayISO } from "@/lib/dates";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { cn, formatDate } from "@/utils";
import type { PaymentMethod, Sale, SaleFilters } from "@/types";

const PRESETS = [
  { id: "hoy", label: "Hoy", range: (): [string, string] => [todayISO(), todayISO()] },
  { id: "7d", label: "Últimos 7 días", range: (): [string, string] => [addDaysISO(todayISO(), -6), todayISO()] },
  { id: "mes", label: "Este mes", range: (): [string, string] => [startOfMonthISO(), todayISO()] },
];

export function SalesPage() {
  const { can } = usePermissions();
  const currency = useGymCurrency();
  const [params, setParams] = useSearchParams();
  const hasRange = params.has("desde") || params.has("hasta");
  const dateFrom = hasRange ? params.get("desde") ?? "" : todayISO();
  const dateTo = hasRange ? params.get("hasta") ?? "" : todayISO();
  const rawMethod = params.get("metodo") ?? "";
  const method = (PAYMENT_METHODS.includes(rawMethod as PaymentMethod) ? rawMethod : "") as PaymentMethod | "";
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);

  const update = useCallback((next: Record<string, string | number | undefined>) => {
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(next)) {
        if (v === undefined || (k === "pagina" && v === 1)) p.delete(k); else p.set(k, String(v));
      }
      return p;
    }, { replace: true });
  }, [setParams]);

  const filters: SaleFilters = {
    date_from: isISODate(dateFrom) ? dateFrom : "", date_to: isISODate(dateTo) ? dateTo : "",
    method, cash_session_id: "", include_voided: true, page, size: 15,
  };
  const sales = useSales(filters);
  const data = sales.data;
  useEffect(() => { if (data && data.pages > 0 && page > data.pages) update({ pagina: data.pages }); }, [data, page, update]);
  const activePreset = useMemo(() => PRESETS.find((p) => { const [a, b] = p.range(); return a === filters.date_from && b === filters.date_to; })?.id,
    [filters.date_from, filters.date_to]);

  const [viewing, setViewing] = useState<Sale | null>(null);
  const [voiding, setVoiding] = useState<Sale | null>(null);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Tienda</h2>
        <p className="mt-1 text-sm text-muted-foreground">Historial de ventas con IVA, tickets y reenvío por WhatsApp.</p>
      </div>
      <PosNav />

      <Card>
        <CardContent className="space-y-5 p-4 sm:p-6">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <Button key={p.id} size="sm" variant={activePreset === p.id ? "gold" : "outline"}
                onClick={() => { const [a, b] = p.range(); update({ desde: a, hasta: b, pagina: 1 }); }}>{p.label}</Button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="s-desde">Desde</Label>
              <Input id="s-desde" type="date" max={todayISO()} value={filters.date_from} className="[color-scheme:dark]"
                onChange={(e) => update({ desde: e.target.value, hasta: filters.date_to, pagina: 1 })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-hasta">Hasta</Label>
              <Input id="s-hasta" type="date" max={todayISO()} value={filters.date_to} className="[color-scheme:dark]"
                onChange={(e) => update({ desde: filters.date_from, hasta: e.target.value, pagina: 1 })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s-metodo">Método</Label>
              <Select id="s-metodo" value={method} onChange={(e) => update({ metodo: e.target.value || undefined, pagina: 1 })}>
                <option value="">Todos</option>
                {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>)}
              </Select>
            </div>
          </div>

          {data && (
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile label="Vendido" value={formatMoney(data.totals.active_total, currency)} tone="gold"
                hint={`${data.totals.active_count} ${data.totals.active_count === 1 ? "venta" : "ventas"}`} />
              <StatTile label="IVA incluido" value={formatMoney(data.totals.active_tax, currency)} hint="Para el libro de ventas" />
              <StatTile label="Anulado" value={formatMoney(data.totals.voided_total, currency)} tone={data.totals.voided_count ? "danger" : "muted"}
                hint={`${data.totals.voided_count} ${data.totals.voided_count === 1 ? "venta" : "ventas"}`} />
            </div>
          )}

          {sales.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : sales.isError ? (
            <div className="space-y-3">
              <ErrorMessage title="No se pudieron cargar las ventas" message={getErrorMessage(sales.error)} />
              <Button variant="outline" size="sm" onClick={() => void sales.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState icon={Receipt} title="Sin ventas en este rango" description="Cambie las fechas o el método." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Venta</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead className="hidden md:table-cell">Productos</TableHead>
                  <TableHead className="hidden sm:table-cell">Método</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="w-20"><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((s) => (
                  <TableRow key={s.id} className={cn(s.is_voided && "opacity-60")}>
                    <TableCell>
                      <p className="font-medium tabular-nums text-foreground">{s.sale_code}</p>
                      {s.is_voided && <Badge variant="destructive" title={s.void_reason ?? ""}>Anulada</Badge>}
                      {s.customer.name && <p className="text-xs text-muted-foreground">{s.customer.name}</p>}
                    </TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {formatDate(s.sale_date)}
                      <p className="text-xs text-muted-foreground">{new Date(s.created_at).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" })}</p>
                    </TableCell>
                    <TableCell className="hidden max-w-xs md:table-cell">
                      <p className="truncate text-sm" title={s.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}>
                        {s.items.map((i) => `${i.quantity}× ${i.product_name}`).join(", ")}
                      </p>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">{PAYMENT_METHOD_LABELS[s.method]}</TableCell>
                    <TableCell className={cn("text-right font-medium tabular-nums text-foreground", s.is_voided && "line-through")}>{formatMoney(s.total, currency)}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-0.5">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                          onClick={() => setViewing(s)} aria-label={`Ver venta ${s.sale_code}`} title="Ver, ticket y WhatsApp">
                          <Eye className="h-4 w-4" />
                        </Button>
                        {can("sales.void") && !s.is_voided && (
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() => setVoiding(s)} aria-label={`Anular ${s.sale_code}`} title="Anular venta">
                            <Ban className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {data && <Pagination page={data.page} pages={data.pages} total={data.total} size={data.size}
            onPageChange={(p) => update({ pagina: p })} disabled={sales.isFetching} />}
        </CardContent>
      </Card>

      <Dialog open={viewing !== null} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Venta {viewing?.sale_code}</DialogTitle>
            <DialogDescription>Reimprima el ticket o reenvíelo por WhatsApp.</DialogDescription>
          </DialogHeader>
          {viewing && <SaleReceipt sale={viewing} currency={currency} />}
        </DialogContent>
      </Dialog>
      <VoidSaleDialog sale={voiding} currency={currency} onOpenChange={(o) => !o && setVoiding(null)} />
    </div>
  );
}
