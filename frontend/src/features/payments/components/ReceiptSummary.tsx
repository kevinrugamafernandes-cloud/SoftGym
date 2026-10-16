import { useState } from "react";
import { FileText, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney, isPositiveAmount } from "@/lib/money";
import { formatDate } from "@/utils";
import type { Payment } from "@/types";
import { WhatsAppDialog } from "@/features/whatsapp/WhatsAppDialog";
import { paymentsService } from "@/services/payments.service";
import { openReceiptPdf } from "../receipt";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right text-foreground">{children}</dd>
    </div>
  );
}

/** Resumen del comprobante con acceso al PDF (para imprimir o enviar al socio). */
export function ReceiptSummary({ payment, currency, memberPhone }: { payment: Payment; currency: string; memberPhone?: string | null }) {
  const [opening, setOpening] = useState(false);
  const [sharing, setSharing] = useState(false);
  const p = payment;
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-input/30 p-4">
        <div className="flex items-baseline justify-between gap-4 border-b border-border pb-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Comprobante</p>
            <p className="text-lg font-semibold tabular-nums text-gold">{p.receipt_code}</p>
          </div>
          <p className="text-2xl font-bold tabular-nums text-foreground">{formatMoney(p.amount, currency)}</p>
        </div>
        <dl className="divide-y divide-border/50 pt-1">
          <Row label="Socio">{p.member.full_name} <span className="text-muted-foreground tabular-nums">· {p.member.identification}</span></Row>
          <Row label="Plan">{p.plan.name}</Row>
          <Row label="Periodo">{formatDate(p.period.start_date)} al {formatDate(p.period.end_date)}</Row>
          <Row label="Método">{PAYMENT_METHOD_LABELS[p.method]}{p.reference ? ` · Ref. ${p.reference}` : ""}</Row>
          {isPositiveAmount(p.discount) && (
            <Row label="Descuento"><span className="text-warning">{formatMoney(p.discount, currency)}</span> <span className="text-muted-foreground">(lista {formatMoney(p.list_price, currency)})</span></Row>
          )}
          <Row label="IVA">{Number(p.tax_rate) > 0
            ? <>{formatMoney(p.tax_amount, currency)} <span className="text-muted-foreground">({Number(p.tax_rate)} % incluido)</span></>
            : "Exento"}</Row>
          <Row label="Fecha del pago">{formatDate(p.payment_date)}</Row>
          {p.registered_by_name && <Row label="Registrado por">{p.registered_by_name}</Row>}
        </dl>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Button
          type="button" variant="outline" loading={opening}
          onClick={async () => { setOpening(true); try { await openReceiptPdf(p.id, p.receipt_code); } finally { setOpening(false); } }}
        >
          <FileText className="mr-2 h-4 w-4" aria-hidden /> Ver / imprimir PDF
        </Button>
        <Button type="button" variant="outline" className="border-success/40 text-success hover:text-success" onClick={() => setSharing(true)}>
          <MessageCircle className="mr-2 h-4 w-4" aria-hidden /> Enviar por WhatsApp
        </Button>
      </div>
      <WhatsAppDialog
        open={sharing} onOpenChange={setSharing} subject={`el comprobante ${p.receipt_code}`} defaultPhone={memberPhone}
        fetchLink={(phone) => paymentsService.whatsapp(p.id, phone)}
      />
    </div>
  );
}
