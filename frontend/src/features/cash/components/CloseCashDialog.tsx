import { useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Lock, TriangleAlert } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCloseCashSession } from "@/hooks/useCashSessions";
import { toast } from "@/hooks/useToast";
import { getErrorCode } from "@/lib/axios";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { CashSession } from "@/types";
import { CRC_DENOMINATIONS, cashDifference } from "../schemas";
import { CashSummaryBreakdown } from "./CashSummaryBreakdown";

interface Props {
  session: CashSession | null;
  onOpenChange: (open: boolean) => void;
}

/** Cierre de turno: conteo físico, sobrante/faltante en vivo y cierre definitivo. */
export function CloseCashDialog({ session, onOpenChange }: Props) {
  const [closed, setClosed] = useState<CashSession | null>(null);
  return (
    // Sigue abierto tras cerrar la caja aunque `session` pase a null (la consulta de la caja actual se
    // refresca al cerrar): así la recepcionista ve el resultado del arqueo.
    <Dialog open={session !== null || closed !== null} onOpenChange={(o) => { if (!o) setClosed(null); onOpenChange(o); }}>
      <DialogContent className="max-w-2xl">
        {closed ? (
          <ClosedResult session={closed} onClose={() => { setClosed(null); onOpenChange(false); }} />
        ) : session ? (
          <CloseForm key={session.id} session={session} onClose={() => onOpenChange(false)} onClosed={setClosed} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function DifferenceBadge({ diff, currency }: { diff: number; currency: string }) {
  if (diff === 0) {
    return <p className="flex items-center gap-2 font-semibold text-success"><CheckCircle2 className="h-4 w-4" aria-hidden /> Caja cuadrada</p>;
  }
  return (
    <p className={cn("flex items-center gap-2 font-semibold", diff > 0 ? "text-warning" : "text-destructive")}>
      <TriangleAlert className="h-4 w-4" aria-hidden />
      <span className="tabular-nums">{`${diff > 0 ? "Sobrante" : "Faltante"} de ${formatMoney(Math.abs(diff), currency)}`}</span>
    </p>
  );
}

function CloseForm({ session, onClose, onClosed }: { session: CashSession; onClose: () => void; onClosed: (s: CashSession) => void }) {
  const closeSession = useCloseCashSession();
  const isCRC = session.currency === "CRC";
  const [mode, setMode] = useState<"total" | "denominaciones">("total");
  const [total, setTotal] = useState("");
  const [counts, setCounts] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notesError, setNotesError] = useState(false);

  const denomTotal = useMemo(
    () => CRC_DENOMINATIONS.reduce((acc, d) => acc + d.value * (Number.parseInt(counts[d.value] ?? "", 10) || 0), 0),
    [counts]
  );
  const counted: number | null =
    mode === "denominaciones" ? denomTotal : total.trim() !== "" && isDecimal(total) ? Number(normalizeDecimal(total)) : null;
  const expected = Number(session.summary.expected_cash);
  const diff = counted === null ? null : cashDifference(counted, expected);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setError(null);
    if (counted === null) {
      setError(mode === "total" ? "Indique el efectivo contado (use números, con hasta 2 decimales)." : "Indique la cantidad de billetes y monedas.");
      return;
    }
    if (diff !== 0 && notes.trim().length === 0) {
      setNotesError(true);
      setError("Hay una diferencia: explique el sobrante o faltante en las observaciones.");
      return;
    }
    const breakdown = mode === "denominaciones"
      ? CRC_DENOMINATIONS.filter((d) => Number(counts[d.value]) > 0).map((d) => `${counts[d.value]}×${d.label}`).join(", ")
      : "";
    const fullNotes = [notes.trim(), breakdown && `Conteo: ${breakdown}`].filter(Boolean).join("\n") || null;
    try {
      const s = await closeSession.mutateAsync({ id: session.id, counted_cash: counted.toFixed(2), notes: fullNotes });
      toast({ variant: Number(s.difference) === 0 ? "success" : "default", title: "Caja cerrada",
        description: Number(s.difference) === 0 ? "El arqueo cuadró."
          : `${Number(s.difference) > 0 ? "Sobrante" : "Faltante"} registrado: ${formatMoney(Math.abs(Number(s.difference)), s.currency)}.` });
      onClosed(s);
    } catch (err) {
      const msg = reportError(err, "No se pudo cerrar la caja");
      setError(msg);
      if (getErrorCode(err) === "closing_notes_required") setNotesError(true);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><Lock className="h-5 w-5 text-gold" aria-hidden /> Cerrar caja</DialogTitle>
        <DialogDescription>
          Cuente el efectivo de la gaveta, incluido el fondo inicial. Turno de {session.cashier.full_name} abierto
          el {new Date(session.opened_at).toLocaleString("es-CR", { dateStyle: "medium", timeStyle: "short" })}
        </DialogDescription>
      </DialogHeader>

      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}

      <CashSummaryBreakdown summary={session.summary} currency={session.currency} openingFloat={session.opening_float} />

      <div className="space-y-3 rounded-lg border border-gold/30 bg-gold/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor="counted-total" className="text-base">Efectivo contado</Label>
          {isCRC && (
            <div className="flex gap-1" role="group" aria-label="Forma de contar">
              <Button type="button" size="sm" variant={mode === "total" ? "gold" : "outline"} onClick={() => setMode("total")}>Total</Button>
              <Button type="button" size="sm" variant={mode === "denominaciones" ? "gold" : "outline"} onClick={() => setMode("denominaciones")}>
                Por billetes y monedas
              </Button>
            </div>
          )}
        </div>

        {mode === "total" ? (
          <Input id="counted-total" inputMode="decimal" autoComplete="off" autoFocus placeholder="0" value={total}
            onChange={(e) => setTotal(e.target.value)} className="tabular-nums text-lg" />
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {CRC_DENOMINATIONS.map((d) => (
              <label key={d.value} className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1.5 text-sm">
                <span className="w-16 shrink-0 tabular-nums text-muted-foreground">{d.label}</span>
                <span className="text-muted-foreground">×</span>
                <Input inputMode="numeric" aria-label={`Cantidad de ${d.kind}s de ${d.label}`} className="h-8 tabular-nums"
                  value={counts[d.value] ?? ""} placeholder="0"
                  onChange={(e) => setCounts((c) => ({ ...c, [d.value]: e.target.value.replace(/\D/g, "").slice(0, 5) }))} />
              </label>
            ))}
            <p className="col-span-full text-right text-sm">Total contado: <strong className="tabular-nums">{formatMoney(denomTotal, session.currency)}</strong></p>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-sm">
          <span className="text-muted-foreground">Esperado: <strong className="tabular-nums text-foreground">{formatMoney(expected, session.currency)}</strong></span>
          {diff !== null && <DifferenceBadge diff={diff} currency={session.currency} />}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="close-notes">
          Observaciones {diff !== null && diff !== 0 ? <span className="text-destructive">*</span> : <span className="text-muted-foreground">(opcional)</span>}
        </Label>
        <Textarea id="close-notes" rows={2} value={notes} aria-invalid={notesError}
          className={notesError ? "border-destructive focus-visible:ring-destructive" : undefined}
          placeholder="Explique cualquier sobrante o faltante"
          onChange={(e) => { setNotes(e.target.value); if (e.target.value.trim()) setNotesError(false); }} />
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={closeSession.isPending}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={closeSession.isPending}>Cerrar caja definitivamente</Button>
      </DialogFooter>
    </form>
  );
}

function ClosedResult({ session, onClose }: { session: CashSession; onClose: () => void }) {
  const diff = Number(session.difference ?? 0);
  return (
    <div className="space-y-4">
      <DialogHeader>
        <DialogTitle>Caja cerrada</DialogTitle>
        <DialogDescription>El arqueo quedó guardado y ya no se puede modificar.</DialogDescription>
      </DialogHeader>
      <dl className="space-y-1 rounded-lg border border-border bg-input/30 p-4 text-sm">
        <div className="flex justify-between"><dt className="text-muted-foreground">Efectivo esperado</dt><dd className="tabular-nums">{formatMoney(session.expected_cash, session.currency)}</dd></div>
        <div className="flex justify-between"><dt className="text-muted-foreground">Efectivo contado</dt><dd className="tabular-nums">{formatMoney(session.counted_cash, session.currency)}</dd></div>
        <div className="flex justify-between border-t border-border pt-2"><dt>Resultado</dt><dd><DifferenceBadge diff={diff} currency={session.currency} /></dd></div>
      </dl>
      <DialogFooter><Button variant="gold" onClick={onClose}>Listo</Button></DialogFooter>
    </div>
  );
}
