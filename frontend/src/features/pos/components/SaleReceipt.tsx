import { useState } from "react";
import { FileText, MessageCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { WhatsAppDialog } from "@/features/whatsapp/WhatsAppDialog";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { salesService } from "@/services/sales.service";
import { cn, formatDate } from "@/utils";
import type { Sale } from "@/types";
import { openSaleTicket } from "../ticket";

/** Comprobante de venta en pantalla con ticket PDF y envío por WhatsApp. */
export function SaleReceipt({ sale, currency, change }: { sale: Sale; currency: string; change?: number | null }) {
  const [opening, setOpening] = useState(false);
  const [sharing, setSharing] = useState(false);
  const m = (v: string | number) => formatMoney(v, currency);

  return (
    <div className="space-y-4">
      <div className={cn("rounded-lg border border-border bg-input/30 p-4", sale.is_voided && "opacity-70")}>
        <div className="flex items-baseline justify-between gap-4 border-b border-border pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Venta</p>
            <p className="text-lg font-semibold tabular-nums text-gold">{sale.sale_code}</p>
            <p className="text-xs text-muted-foreground">{formatDate(sale.sale_date)} · {sale.cashier_name ?? "—"}</p>
          </div>
          <p className={cn("text-2xl font-bold tabular-nums text-foreground", sale.is_voided && "line-through")}>{m(sale.total)}</p>
        </div>
        <ul className="divide-y divide-border/50 py-1 text-sm">
          {sale.items.map((i) => (
            <li key={i.product_id} className="flex justify-between gap-3 py-1.5">
              <span className="min-w-0"><span className="tabular-nums text-muted-foreground">{i.quantity} ×</span> {i.product_name}
                {Number(i.tax_rate) === 0 && <span className="ml-1 text-xs text-muted-foreground">(exento)</span>}</span>
              <span className="shrink-0 tabular-nums">{m(i.line_total)}</span>
            </li>
          ))}
        </ul>
        <dl className="space-y-0.5 border-t border-border pt-2 text-sm">
          <div className="flex justify-between text-muted-foreground"><dt>Subtotal sin IVA</dt><dd className="tabular-nums">{m(sale.subtotal)}</dd></div>
          {sale.taxes.filter((t) => Number(t.tax) > 0).map((t) => (
            <div key={t.rate} className="flex justify-between text-muted-foreground"><dt>IVA {Number(t.rate)} %</dt><dd className="tabular-nums">{m(t.tax)}</dd></div>
          ))}
          <div className="flex justify-between font-semibold"><dt>Total</dt><dd className="tabular-nums">{m(sale.total)}</dd></div>
          <div className="flex justify-between text-muted-foreground"><dt>Pago</dt><dd>{PAYMENT_METHOD_LABELS[sale.method]}{sale.reference ? ` · Ref. ${sale.reference}` : ""}</dd></div>
          {change !== undefined && change !== null && change > 0 && (
            <div className="flex justify-between text-base font-semibold text-success"><dt>Vuelto</dt><dd className="tabular-nums">{m(change)}</dd></div>
          )}
          {sale.customer.name && <div className="flex justify-between text-muted-foreground"><dt>Cliente</dt><dd>{sale.customer.name}</dd></div>}
        </dl>
        {sale.is_voided && (
          <p className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
            Anulada{sale.voided_by_name ? ` por ${sale.voided_by_name}` : ""}: {sale.void_reason}
          </p>
        )}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <Button type="button" variant="outline" loading={opening}
          onClick={async () => { setOpening(true); try { await openSaleTicket(sale); } finally { setOpening(false); } }}>
          <FileText className="mr-2 h-4 w-4" aria-hidden /> Ticket PDF
        </Button>
        <Button type="button" variant="outline" className="border-success/40 text-success hover:text-success" onClick={() => setSharing(true)}>
          <MessageCircle className="mr-2 h-4 w-4" aria-hidden /> Enviar por WhatsApp
        </Button>
      </div>
      <WhatsAppDialog open={sharing} onOpenChange={setSharing} subject={`el comprobante ${sale.sale_code}`}
        defaultPhone={sale.customer.phone} fetchLink={(phone) => salesService.whatsapp(sale.id, phone)} />
    </div>
  );
}
