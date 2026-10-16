import { openPdf } from "@/lib/pdf";
import { salesService } from "@/services/sales.service";
import type { Sale } from "@/types";

/** Abre el ticket PDF (80 mm) de una venta en una pestaña nueva. */
export function openSaleTicket(sale: Pick<Sale, "id" | "sale_code">): Promise<void> {
  return openPdf(() => salesService.ticketPdf(sale.id), `Venta ${sale.sale_code}`, `venta-${sale.sale_code}.pdf`);
}
