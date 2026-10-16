import { useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Unlock } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useOpenCashSession } from "@/hooks/useCashSessions";
import { toast } from "@/hooks/useToast";
import { describeInvalidFields } from "@/lib/form-errors";
import { formatMoney } from "@/lib/money";
import { normalizeDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { CashSession } from "@/types";
import { openCashSchema, type OpenCashValues } from "../schemas";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onOpened?: (session: CashSession) => void;
}

/** Apertura de caja: el fondo inicial (caja chica) con que arranca el turno. */
export function OpenCashDialog({ open, onOpenChange, onOpened }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Unlock className="h-5 w-5 text-gold" aria-hidden /> Abrir caja</DialogTitle>
          <DialogDescription>
            Cuente el dinero con que inicia el turno. Los cobros y ventas que registre quedarán en esta caja hasta que la cierre.
          </DialogDescription>
        </DialogHeader>
        {open && <OpenForm onClose={() => onOpenChange(false)} onOpened={onOpened} />}
      </DialogContent>
    </Dialog>
  );
}

function OpenForm({ onClose, onOpened }: { onClose: () => void; onOpened?: (s: CashSession) => void }) {
  const openSession = useOpenCashSession();
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<OpenCashValues>({
    resolver: zodResolver(openCashSchema),
    defaultValues: { opening_float: "", notes: "" },
  });

  const onSubmit = async (v: OpenCashValues) => {
    setFormError(null);
    try {
      const s = await openSession.mutateAsync({ opening_float: normalizeDecimal(v.opening_float), notes: v.notes || null });
      toast({ variant: "success", title: "Caja abierta", description: `Fondo inicial: ${formatMoney(s.opening_float, s.currency)}.` });
      onOpened?.(s);
      onClose();
    } catch (err) {
      setFormError(reportError(err, "No se pudo abrir la caja"));
    }
  };

  return (
    <form
      // stopPropagation: este diálogo puede abrirse desde OTRO formulario (el de cobro) y, aunque el
      // portal lo saque del DOM, el evento submit de React se propagaría a ese formulario.
      onSubmit={(e) => { e.stopPropagation(); void handleSubmit(onSubmit, (f: FieldErrors<OpenCashValues>) => setFormError(describeInvalidFields(f)))(e); }}
      noValidate className="space-y-4"
    >
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="opening_float">Fondo inicial (₡)</Label>
        <Input id="opening_float" inputMode="decimal" autoComplete="off" autoFocus placeholder="0"
          aria-invalid={Boolean(errors.opening_float)}
          className={cn("tabular-nums text-lg", errors.opening_float && "border-destructive focus-visible:ring-destructive")}
          {...register("opening_float")} />
        {errors.opening_float && <p className="text-xs text-destructive">{errors.opening_float.message}</p>}
        <p className="text-xs text-muted-foreground">Escriba 0 si inicia sin dinero en la gaveta.</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="open-notes">Observaciones <span className="text-muted-foreground">(opcional)</span></Label>
        <Textarea id="open-notes" rows={2} placeholder="Ej.: 5 billetes de ₡2 000 y monedas" {...register("notes")} />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={isSubmitting}>Abrir caja</Button>
      </DialogFooter>
    </form>
  );
}
