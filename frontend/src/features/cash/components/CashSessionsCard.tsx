import { useState } from "react";
import { Lock, RefreshCw } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { useAuth, usePermissions } from "@/features/auth";
import { useCashSession, useCashSessions } from "@/hooks/useCashSessions";
import { getErrorMessage } from "@/lib/axios";
import { formatMoney } from "@/lib/money";
import { cn } from "@/utils";
import { CashSummaryBreakdown } from "./CashSummaryBreakdown";
import { CloseCashDialog } from "./CloseCashDialog";

const time = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString("es-CR", { hour: "2-digit", minute: "2-digit" }) : "—");

function DiffCell({ value, currency }: { value: string | null; currency: string }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  const n = Number(value);
  return (
    <span className={cn("font-medium tabular-nums", n === 0 ? "text-success" : n > 0 ? "text-warning" : "text-destructive")}>
      {n === 0 ? "Cuadrada" : `${n > 0 ? "+" : "−"}${formatMoney(Math.abs(n), currency)}`}
    </span>
  );
}

/** Turnos de caja de un día (la recepcionista ve los suyos; el administrador, todos). */
export function CashSessionsCard({ day, currency }: { day: string; currency: string }) {
  const { can } = usePermissions();
  const sessions = useCashSessions({ date_from: day, date_to: day, status: "", page: 1, size: 50 });
  const [selected, setSelected] = useState<string | null>(null);
  const items = sessions.data?.items ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{can("cash.all") ? "Turnos de caja del día" : "Mis turnos del día"}</CardTitle>
      </CardHeader>
      <CardContent>
        {sessions.isLoading ? (
          <Skeleton className="h-24" />
        ) : sessions.isError ? (
          <div className="space-y-3">
            <ErrorMessage title="No se pudieron cargar los turnos" message={getErrorMessage(sessions.error)} />
            <Button variant="outline" size="sm" onClick={() => void sessions.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
          </div>
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No se abrió caja este día.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Cajero</TableHead>
                <TableHead>Horario</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Fondo</TableHead>
                <TableHead className="hidden text-right md:table-cell">Esperado</TableHead>
                <TableHead className="hidden text-right md:table-cell">Contado</TableHead>
                <TableHead className="text-right">Arqueo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.id} className="cursor-pointer" onClick={() => setSelected(s.id)}
                  tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") setSelected(s.id); }} aria-label={`Ver turno de ${s.cashier.full_name}`}>
                  <TableCell className="font-medium text-foreground">{s.cashier.full_name}</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {time(s.opened_at)} – {s.status === "abierta" ? <Badge variant="success">Abierta</Badge> : time(s.closed_at)}
                  </TableCell>
                  <TableCell className="hidden text-right tabular-nums sm:table-cell">{formatMoney(s.opening_float, currency)}</TableCell>
                  <TableCell className="hidden text-right tabular-nums md:table-cell">{s.expected_cash ? formatMoney(s.expected_cash, currency) : "—"}</TableCell>
                  <TableCell className="hidden text-right tabular-nums md:table-cell">{s.counted_cash ? formatMoney(s.counted_cash, currency) : "—"}</TableCell>
                  <TableCell className="text-right">{s.status === "abierta" ? <span className="text-xs text-muted-foreground">En curso</span> : <DiffCell value={s.difference} currency={currency} />}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <SessionDetailDialog id={selected} onOpenChange={(o) => !o && setSelected(null)} />
    </Card>
  );
}

function SessionDetailDialog({ id, onOpenChange }: { id: string | null; onOpenChange: (o: boolean) => void }) {
  const { user } = useAuth();
  const { can } = usePermissions();
  const detail = useCashSession(id);
  const [closing, setClosing] = useState(false);
  const s = detail.data;
  const canClose = s?.status === "abierta" && (s.cashier.id === user?.id || can("cash.all"));

  return (
    <>
      <Dialog open={id !== null && !closing} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Turno de {s?.cashier.full_name ?? "…"}</DialogTitle>
            <DialogDescription>
              {s ? <>Abierto {new Date(s.opened_at).toLocaleString("es-CR", { dateStyle: "medium", timeStyle: "short" })}
                {s.closed_at && <> · cerrado {new Date(s.closed_at).toLocaleString("es-CR", { timeStyle: "short" })}{s.closed_by_name && s.closed_by_name !== s.cashier.full_name ? ` por ${s.closed_by_name}` : ""}</>}</> : "Cargando…"}
            </DialogDescription>
          </DialogHeader>
          {detail.isLoading && <Skeleton className="h-40" />}
          {detail.isError && <p className="text-sm text-destructive">{getErrorMessage(detail.error)}</p>}
          {s && (
            <div className="space-y-4">
              {s.status === "cerrada" && (
                <dl className="grid gap-2 rounded-lg border border-gold/30 bg-gold/5 p-3 text-sm sm:grid-cols-3">
                  <div><dt className="text-xs text-muted-foreground">Esperado al cierre</dt><dd className="tabular-nums">{formatMoney(s.expected_cash, s.currency)}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Contado</dt><dd className="tabular-nums">{formatMoney(s.counted_cash, s.currency)}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Resultado</dt><dd><DiffCell value={s.difference} currency={s.currency} /></dd></div>
                  {s.closing_notes && <p className="whitespace-pre-line text-xs text-muted-foreground sm:col-span-3">{s.closing_notes}</p>}
                </dl>
              )}
              {s.opening_notes && <p className="text-xs text-muted-foreground">Apertura: {s.opening_notes}</p>}
              <CashSummaryBreakdown summary={s.summary} currency={s.currency} openingFloat={s.opening_float} />
              {s.status === "cerrada" && s.summary.expected_cash !== s.expected_cash && (
                <p className="text-xs text-muted-foreground">El desglose se calcula hoy (excluye anulaciones posteriores al cierre); el arqueo guardado no cambia.</p>
              )}
            </div>
          )}
          {canClose && (
            <DialogFooter>
              <Button variant="gold" onClick={() => setClosing(true)}><Lock className="mr-2 h-4 w-4" aria-hidden /> Cerrar este turno</Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
      <CloseCashDialog session={closing && s ? s : null} onOpenChange={(o) => { if (!o) { setClosing(false); onOpenChange(false); } }} />
    </>
  );
}
