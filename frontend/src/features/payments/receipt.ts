import { openPdf } from "@/lib/pdf";
import { paymentsService } from "@/services/payments.service";

/** Abre el comprobante PDF de un pago de membresía en una pestaña nueva. */
export function openReceiptPdf(paymentId: string, receiptCode: string): Promise<void> {
  return openPdf(() => paymentsService.receiptPdf(paymentId), `Comprobante ${receiptCode}`, `comprobante-${receiptCode}.pdf`);
}
