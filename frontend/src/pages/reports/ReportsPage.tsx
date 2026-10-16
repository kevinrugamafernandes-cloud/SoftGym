import { useMemo, useState } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, FileSpreadsheet, FileText, Lock, LockOpen, RefreshCw } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { StatTile } from "@/components/common/StatTile";
import { useCloseMonth, useMonthlyCloses, useMonthlyReport, useSalesBook } from "@/hooks/useAdmin";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { downloadFile, openPdf } from "@/lib/pdf";
import { reportError } from "@/lib/report-error";
import { reportsService } from "@/services/admin.service";
import { cn, formatDate } from "@/utils";
import type { DocType, MonthlyReport } from "@/types";

const PAGE = 50;
const rateLabel = (r: string) => (Number(r) === 0 ? "Exento" : `${Number(r)} %`);
const TYPE_LABEL: Record<DocType, string> = { membresia: "Membresías", venta: "Tienda" };

function CloseMonthDialog({ report, open, onOpenChange }: { report: MonthlyReport; open: boolean; onOpenChange: (o: boolean) => void }) {
  const close = useCloseMonth();
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setError(null);
    try {
      await close.mutateAsync({ year: report.year, month: report.month, notes: notes.trim() || null });
      toast({ variant: "success", title: `${report.label} cerrado`, description: "Descargue el PDF y el CSV para el contador." });
      onOpenChange(false);
    } catch (err) {
      setError(reportError(err, "No se pudo cerrar el mes"));
    }
  };
  const s = report.summary;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Cerrar {report.label}</DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-2">
              <p>Se guardarán los totales tal como están y el mes quedará <strong className="text-foreground">bloqueado</strong>:
                no se podrán registrar cobros con fecha de ese mes ni anular sus cobros o ventas.</p>
              <p className="tabular-nums text-foreground">Total {formatMoney(s.total, s.currency)} · IVA {formatMoney(s.tax_total, s.currency)} · {s.count} documentos</p>
            </div>
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}><AlertDescription className="text-foreground">{error}</AlertDescription></Alert>}
        <div className="space-y-1.5">
          <Label htmlFor="close-notes">Observaciones <span className="text-muted-foreground">(opcional)</span></Label>
          <Textarea id="close-notes" rows={2} maxLength={1000} value={notes} placeholder="Ej.: entregado al contador el 05/11"
            onChange={(e) => setNotes(e.target.value)} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={close.isPending}>Cancelar</Button>
          <Button variant="gold" onClick={() => void submit()} loading={close.isPending}><Lock className="mr-2 h-4 w-4" aria-hidden /> Cerrar mes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ReportsPage() {
  const now = new Date();
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const shift = (delta: number) => setYm(({ year, month }) => {
    const d = new Date(year, month - 1 + delta, 1);
    return { year: d.getFullYear(), month: d.getMonth() + 1 };
  });
  const isFuture = ym.year > now.getFullYear() || (ym.year === now.getFullYear() && ym.month >= now.getMonth() + 1);

  const report = useMonthlyReport(ym.year, ym.month);
  const r = report.data;
  const book = useSalesBook(r?.date_from ?? "", r?.date_to ?? "", Boolean(r));
  const closes = useMonthlyCloses();
  const [closing, setClosing] = useState(false);
  const [exporting, setExporting] = useState<"pdf" | "csv" | null>(null);

  const [type, setType] = useState<DocType | "">("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (book.data?.rows ?? []).filter((x) => (!type || x.doc_type === type) &&
      (!q || `${x.document} ${x.customer ?? ""} ${x.identification ?? ""} ${x.detail}`.toLowerCase().includes(q)));
  }, [book.data, type, search]);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const shown = rows.slice((Math.min(page, pages) - 1) * PAGE, Math.min(page, pages) * PAGE);

  const s = r?.summary;
  const m = (v: string | number) => formatMoney(v, s?.currency ?? "CRC");
  const fileBase = `${ym.year}-${String(ym.month).padStart(2, "0")}`;

  const exportPdf = async () => {
    setExporting("pdf");
    try { await openPdf(() => reportsService.monthlyPdf(ym.year, ym.month), `Cierre ${r?.label ?? ""}`, `cierre-${fileBase}.pdf`); }
    finally { setExporting(null); }
  };
  const exportCsv = async () => {
    if (!r) return;
    setExporting("csv");
    try { await downloadFile(() => reportsService.salesBookCsv(r.date_from, r.date_to), `libro-ventas_${fileBase}.csv`); }
    finally { setExporting(null); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Reportes y cierre mensual</h2>
          <p className="mt-1 text-sm text-muted-foreground">Libro de ventas con IVA por tarifa: membresías y tienda en un solo reporte para el contador.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void exportCsv()} loading={exporting === "csv"} disabled={!r}>
            <FileSpreadsheet className="mr-2 h-4 w-4" aria-hidden /> CSV (Excel)
          </Button>
          <Button variant="outline" onClick={() => void exportPdf()} loading={exporting === "pdf"} disabled={!r}>
            <FileText className="mr-2 h-4 w-4" aria-hidden /> PDF para el contador
          </Button>
        </div>
      </div>

      {/* Selector de mes */}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" aria-label="Mes anterior" onClick={() => shift(-1)}><ChevronLeft className="h-4 w-4" /></Button>
        <p className="min-w-40 text-center text-lg font-semibold capitalize text-foreground">{r?.label ?? "…"}</p>
        <Button variant="outline" size="icon" aria-label="Mes siguiente" onClick={() => shift(1)} disabled={isFuture}><ChevronRight className="h-4 w-4" /></Button>
        {r && (r.status === "cerrado"
          ? <Badge variant="success" className="gap-1"><Lock className="h-3 w-3" aria-hidden /> Cerrado</Badge>
          : r.status === "en_curso" ? <Badge variant="gold">En curso</Badge>
          : <Badge variant="warning" className="gap-1"><LockOpen className="h-3 w-3" aria-hidden /> Sin cerrar</Badge>)}
      </div>

      {report.isLoading ? <Skeleton className="h-64" /> : report.isError || !r || !s ? (
        <div className="space-y-3">
          <ErrorMessage title="No se pudo cargar el reporte" message={getErrorMessage(report.error)} />
          <Button variant="outline" size="sm" onClick={() => void report.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
        </div>
      ) : (
        <>
          {r.status === "cerrado" ? (
            <Alert variant="success" icon={<Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
              <AlertTitle>Mes cerrado el {r.closed_at ? new Date(r.closed_at).toLocaleString("es-CR", { dateStyle: "medium", timeStyle: "short" }) : ""}{r.closed_by_name ? ` por ${r.closed_by_name}` : ""}</AlertTitle>
              <AlertDescription>Las cifras son las entregadas al contador y el periodo está bloqueado.{r.notes ? ` Observaciones: ${r.notes}` : ""}</AlertDescription>
            </Alert>
          ) : (
            <Alert variant={r.can_close ? "info" : "warning"} icon={<LockOpen className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
              <AlertTitle>{r.can_close ? "Listo para cerrar" : "Cifras provisionales"}</AlertTitle>
              <AlertDescription>
                {r.can_close ? "Revise el resumen y cierre el mes para entregarlo al contador." : r.close_blockers.join(" · ")}
              </AlertDescription>
              {r.can_close && (
                <div className="pt-2"><Button size="sm" variant="gold" onClick={() => setClosing(true)}><Lock className="mr-2 h-4 w-4" aria-hidden /> Cerrar {r.label}</Button></div>
              )}
            </Alert>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Total del mes" value={m(s.total)} tone="gold" hint={`${s.count} ${s.count === 1 ? "documento" : "documentos"} · IVA incluido`} />
            <StatTile label="Base imponible" value={m(s.subtotal)} hint="Sin IVA" />
            <StatTile label="IVA" value={m(s.tax_total)} hint="Débito fiscal del periodo" />
            <StatTile label="Anulado" value={m(s.voided_total)} tone={s.voided_count ? "danger" : "muted"} hint={`${s.voided_count} ${s.voided_count === 1 ? "documento" : "documentos"} (no suman)`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base">IVA por tarifa</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow className="hover:bg-transparent"><TableHead>Tarifa</TableHead><TableHead className="text-right">Base</TableHead><TableHead className="text-right">IVA</TableHead><TableHead className="text-right">Total</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {s.by_rate.map((x) => (
                      <TableRow key={x.rate}><TableCell className="font-medium">{rateLabel(x.rate)}</TableCell><TableCell className="text-right tabular-nums">{m(x.base)}</TableCell><TableCell className="text-right tabular-nums">{m(x.tax)}</TableCell><TableCell className="text-right tabular-nums">{m(x.total)}</TableCell></TableRow>
                    ))}
                    <TableRow className="hover:bg-transparent font-semibold"><TableCell>Total</TableCell><TableCell className="text-right tabular-nums">{m(s.subtotal)}</TableCell><TableCell className="text-right tabular-nums">{m(s.tax_total)}</TableCell><TableCell className="text-right tabular-nums text-gold">{m(s.total)}</TableCell></TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base">Ingresos por tipo y método</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <Table>
                  <TableBody>
                    {s.by_type.map((x) => (
                      <TableRow key={x.doc_type}><TableCell className="font-medium">{TYPE_LABEL[x.doc_type]} <span className="text-xs text-muted-foreground">({x.count})</span></TableCell><TableCell className="text-right text-xs text-muted-foreground tabular-nums">IVA {m(x.tax_total)}</TableCell><TableCell className="text-right tabular-nums">{m(x.total)}</TableCell></TableRow>
                    ))}
                  </TableBody>
                </Table>
                <div className="flex flex-wrap gap-2 text-sm">
                  {s.by_method.map((x) => (
                    <span key={x.method} className="rounded-full border border-border bg-input/30 px-3 py-1">{PAYMENT_METHOD_LABELS[x.method]}: <strong className="tabular-nums">{m(x.total)}</strong></span>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground">
                  Arqueos: {s.cash_sessions.count} turnos · faltantes <span className="tabular-nums text-destructive">{m(s.cash_sessions.shortages_total)}</span> ·
                  sobrantes <span className="tabular-nums text-warning">{m(s.cash_sessions.overages_total)}</span>
                  {s.cash_sessions.open_count > 0 && <> · <span className="text-warning">{s.cash_sessions.open_count} abiertos</span></>}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Libro de ventas</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
                <SearchInput value={search} onValueChange={(v) => { setSearch(v); setPage(1); }} placeholder="Buscar documento, cliente o detalle…" aria-label="Buscar en el libro" />
                <Select aria-label="Tipo de documento" value={type} onChange={(e) => { setType(e.target.value as DocType | ""); setPage(1); }}>
                  <option value="">Membresías y tienda</option><option value="membresia">Solo membresías</option><option value="venta">Solo tienda</option>
                </Select>
              </div>
              {book.isLoading ? <Skeleton className="h-40" /> : book.isError ? (
                <ErrorMessage title="No se pudo cargar el libro" message={getErrorMessage(book.error)} />
              ) : rows.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">Sin movimientos en este periodo.</p>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead>Fecha</TableHead><TableHead>Documento</TableHead><TableHead className="hidden md:table-cell">Cliente / detalle</TableHead>
                        <TableHead className="hidden sm:table-cell">IVA</TableHead><TableHead className="text-right">Base</TableHead>
                        <TableHead className="text-right">IVA</TableHead><TableHead className="text-right">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {shown.map((x) => (
                        <TableRow key={x.document} className={cn(x.voided && "opacity-60")}>
                          <TableCell className="whitespace-nowrap tabular-nums">{formatDate(x.date, { day: "2-digit", month: "short" })}</TableCell>
                          <TableCell>
                            <p className="font-medium tabular-nums">{x.document}</p>
                            {x.voided ? <Badge variant="destructive" title={x.void_reason ?? ""}>Anulado</Badge>
                              : <p className="text-xs text-muted-foreground">{PAYMENT_METHOD_LABELS[x.method]}</p>}
                          </TableCell>
                          <TableCell className="hidden max-w-xs md:table-cell">
                            <p className="truncate">{x.customer ?? "—"}</p>
                            <p className="truncate text-xs text-muted-foreground" title={x.detail}>{x.detail}</p>
                          </TableCell>
                          <TableCell className="hidden whitespace-nowrap text-xs sm:table-cell">{x.taxes.map((t) => rateLabel(t.rate)).join(" + ")}</TableCell>
                          <TableCell className={cn("text-right tabular-nums", x.voided && "line-through")}>{m(x.subtotal)}</TableCell>
                          <TableCell className={cn("text-right tabular-nums", x.voided && "line-through")}>{m(x.tax_total)}</TableCell>
                          <TableCell className={cn("text-right font-medium tabular-nums", x.voided && "line-through")}>{m(x.total)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <Pagination page={Math.min(page, pages)} pages={pages} total={rows.length} size={PAGE} onPageChange={setPage} />
                </>
              )}
            </CardContent>
          </Card>

          {closes.data && closes.data.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-base">Meses cerrados</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {closes.data.map((c) => (
                  <button key={c.id} type="button" onClick={() => setYm({ year: c.year, month: c.month })}
                    className="rounded-lg border border-border bg-input/30 px-3 py-2 text-left text-sm hover:border-gold/40">
                    <p className="font-medium capitalize">{c.label}</p>
                    <p className="text-xs tabular-nums text-muted-foreground">{m(c.total)} · {c.closed_by_name ?? "—"}</p>
                  </button>
                ))}
              </CardContent>
            </Card>
          )}

          <CloseMonthDialog report={r} open={closing} onOpenChange={setClosing} />
        </>
      )}
    </div>
  );
}
