import { useState } from "react";
import { Lock, Unlock, Wallet } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { usePermissions } from "@/features/auth";
import { useCurrentCashSession } from "@/hooks/useCashSessions";
import { formatMoney } from "@/lib/money";
import { cn } from "@/utils";
import { CashSummaryBreakdown } from "./CashSummaryBreakdown";
import { CloseCashDialog } from "./CloseCashDialog";
import { OpenCashDialog } from "./OpenCashDialog";

/** Estado de la caja del usuario en el encabezado: abrir, ver el turno y cerrar. */
export function CashSessionIndicator() {
  const { can } = usePermissions();
  const current = useCurrentCashSession();
  const [opening, setOpening] = useState(false);
  const [viewing, setViewing] = useState(false);
  const [closing, setClosing] = useState(false);
  if (!can("cash.view") || current.isLoading) return null;
  const s = current.data ?? null;

  return (
    <>
      {s ? (
        <Button variant="outline" size="sm" onClick={() => setViewing(true)}
          className="gap-2 border-success/40 text-success hover:text-success" title="Ver mi turno de caja">
          <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-success" /></span>
          <span className="hidden md:inline">Caja abierta</span>
          <span className="hidden tabular-nums text-foreground lg:inline">· {formatMoney(s.summary.expected_cash, s.currency)}</span>
        </Button>
      ) : (
        <Button variant="outline" size="sm" onClick={() => setOpening(true)}
          className="gap-2 border-warning/40 text-warning hover:text-warning" title="Abrir caja">
          <Lock className="h-3.5 w-3.5" aria-hidden /> <span className="hidden md:inline">Caja cerrada · Abrir</span>
        </Button>
      )}

      <OpenCashDialog open={opening} onOpenChange={setOpening} />

      <Dialog open={viewing && s !== null} onOpenChange={setViewing}>
        <DialogContent className="max-w-2xl">
          {s && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2"><Wallet className="h-5 w-5 text-gold" aria-hidden /> Mi turno de caja</DialogTitle>
                <DialogDescription>
                  Abierta el {new Date(s.opened_at).toLocaleString("es-CR", { dateStyle: "medium", timeStyle: "short" })} con
                  {" "}{formatMoney(s.opening_float, s.currency)} de fondo.
                </DialogDescription>
              </DialogHeader>
              <CashSummaryBreakdown summary={s.summary} currency={s.currency} openingFloat={s.opening_float} />
              <DialogFooter>
                <Button variant="outline" onClick={() => setViewing(false)}>Seguir trabajando</Button>
                <Button variant="gold" onClick={() => { setViewing(false); setClosing(true); }}>
                  <Lock className="mr-2 h-4 w-4" aria-hidden /> Cerrar caja
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <CloseCashDialog session={closing ? s : null} onOpenChange={(o) => !o && setClosing(false)} />
    </>
  );
}

/** Aviso para pantallas que cobran: sin caja abierta no se puede cobrar ni vender. */
export function NoCashSessionAlert({ className, action = "cobrar" }: { className?: string; action?: string }) {
  const [opening, setOpening] = useState(false);
  return (
    <div className={cn("flex flex-col gap-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm sm:flex-row sm:items-center sm:justify-between", className)} role="alert">
      <p className="flex items-center gap-2 text-foreground">
        <Lock className="h-4 w-4 shrink-0 text-warning" aria-hidden />
        No tiene una caja abierta. Ábrala con el fondo inicial para {action}.
      </p>
      <Button type="button" size="sm" variant="gold" onClick={() => setOpening(true)} className="shrink-0">
        <Unlock className="mr-2 h-4 w-4" aria-hidden /> Abrir caja
      </Button>
      <OpenCashDialog open={opening} onOpenChange={setOpening} />
    </div>
  );
}
