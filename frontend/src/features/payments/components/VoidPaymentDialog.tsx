import { useState } from "react";
import { AlertCircle } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useVoidPayment } from "@/hooks/usePayments";
import { toast } from "@/hooks/useToast";
import { getErrorCode } from "@/lib/axios";
import { formatMoney } from "@/lib/money";
import { reportError } from "@/lib/report-error";
import type { Payment } from "@/types";

interface VoidPaymentDialogProps {
  payment: Payment | null;
  currency: string;
  onOpenChange: (open: boolean) => void;
}

/**
 * Anulación de un pago (solo administradores). El pago NO se borra: queda marcado como
 * anulado con quién, cuándo y por qué, y la membresía que generó se cancela.
 */
export function VoidPaymentDialog({ payment, currency, onOpenChange }: VoidPaymentDialogProps) {
  return (
    <Dialog open={payment !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        {payment && <VoidForm key={payment.id} payment={payment} currency={currency} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function VoidForm({ payment, currency, onClose }: { payment: Payment; currency: string; onClose: () => void }) {
  const voidPayment = useVoidPayment();
  const [reason, setReason] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmed = reason.trim();
    if (trimmed.length < 5) {
      setFieldError("Indique el motivo de la anulación (mínimo 5 caracteres)");
      return;
    }
    setFieldError(null);
    try {
      await voidPayment.mutateAsync({ id: payment.id, reason: trimmed });
      toast({
        variant: "success",
        title: `Pago ${payment.receipt_code} anulado`,
        description: `La membresía asociada se canceló y el estado de ${payment.member.full_name} se recalculó.`,
      });
      onClose();
    } catch (err) {
      const msg = reportError(err, "No se pudo anular el pago");
      setError(
        getErrorCode(err) === "void_latest_first"
          ? `${msg}. Revise el historial del socio: debe anular los pagos en orden, del más reciente al más antiguo.`
          : msg
      );
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <DialogHeader>
        <DialogTitle>Anular pago {payment.receipt_code}</DialogTitle>
        <DialogDescription asChild>
          <div>
            {payment.member.full_name} · {payment.plan.name} · <strong className="text-foreground">{formatMoney(payment.amount, currency)}</strong>.
            El pago quedará registrado como anulado (no se borra) y el periodo de membresía que generó se cancelará.
          </div>
        </DialogDescription>
      </DialogHeader>

      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="void-reason">Motivo de la anulación</Label>
        <Textarea
          id="void-reason" rows={3} maxLength={500} autoFocus value={reason}
          placeholder="Ej.: cobro registrado al socio equivocado"
          aria-invalid={Boolean(fieldError)}
          className={fieldError ? "border-destructive focus-visible:ring-destructive" : undefined}
          onChange={(e) => setReason(e.target.value)}
        />
        {fieldError && <p className="text-xs text-destructive">{fieldError}</p>}
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={voidPayment.isPending}>Cancelar</Button>
        <Button type="submit" variant="destructive" loading={voidPayment.isPending}>Anular pago</Button>
      </DialogFooter>
    </form>
  );
}
