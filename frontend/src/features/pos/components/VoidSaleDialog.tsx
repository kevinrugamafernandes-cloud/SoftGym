import { useState } from "react";
import { AlertCircle } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useVoidSale } from "@/hooks/useSales";
import { toast } from "@/hooks/useToast";
import { formatMoney } from "@/lib/money";
import { reportError } from "@/lib/report-error";
import type { Sale } from "@/types";

/** Anulación de una venta (administrador): no se borra y la mercadería vuelve al inventario. */
export function VoidSaleDialog({ sale, currency, onOpenChange }: { sale: Sale | null; currency: string; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={sale !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        {sale && <VoidForm key={sale.id} sale={sale} currency={currency} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function VoidForm({ sale, currency, onClose }: { sale: Sale; currency: string; onClose: () => void }) {
  const voidSale = useVoidSale();
  const [reason, setReason] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (reason.trim().length < 5) return setFieldError("Indique el motivo de la anulación (mínimo 5 caracteres)");
    setFieldError(null);
    try {
      await voidSale.mutateAsync({ id: sale.id, reason: reason.trim() });
      toast({ variant: "success", title: `Venta ${sale.sale_code} anulada`, description: "Los productos volvieron al inventario." });
      onClose();
    } catch (err) {
      setError(reportError(err, "No se pudo anular la venta"));
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <DialogHeader>
        <DialogTitle>Anular venta {sale.sale_code}</DialogTitle>
        <DialogDescription asChild>
          <div>
            {sale.items.length} {sale.items.length === 1 ? "producto" : "productos"} · <strong className="text-foreground">{formatMoney(sale.total, currency)}</strong>.
            La venta queda registrada como anulada y las unidades vuelven al stock.
          </div>
        </DialogDescription>
      </DialogHeader>
      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="void-sale-reason">Motivo de la anulación</Label>
        <Textarea id="void-sale-reason" rows={3} maxLength={500} autoFocus value={reason} placeholder="Ej.: el cliente devolvió el producto sellado"
          aria-invalid={Boolean(fieldError)} className={fieldError ? "border-destructive focus-visible:ring-destructive" : undefined}
          onChange={(e) => setReason(e.target.value)} />
        {fieldError && <p className="text-xs text-destructive">{fieldError}</p>}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={voidSale.isPending}>Cancelar</Button>
        <Button type="submit" variant="destructive" loading={voidSale.isPending}>Anular venta</Button>
      </DialogFooter>
    </form>
  );
}
