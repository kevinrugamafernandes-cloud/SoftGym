import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import type { CashSessionSummary } from "@/types";

/** Desglose de un turno: por método, separando membresías y tienda. */
export function CashSummaryBreakdown({ summary, currency, openingFloat }: {
  summary: CashSessionSummary; currency: string; openingFloat: string;
}) {
  const m = (v: string | number) => formatMoney(v, currency);
  return (
    <div className="space-y-3">
      {summary.by_method.length === 0 ? (
        <p className="rounded-lg border border-border bg-input/30 p-3 text-center text-sm text-muted-foreground">
          Aún no hay cobros ni ventas en este turno.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Método</TableHead>
              <TableHead className="text-right">Membresías</TableHead>
              <TableHead className="text-right">Tienda</TableHead>
              <TableHead className="text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summary.by_method.map((r) => (
              <TableRow key={r.method}>
                <TableCell className="font-medium text-foreground">{PAYMENT_METHOD_LABELS[r.method]}</TableCell>
                <TableCell className="text-right tabular-nums">{m(r.payments_total)} <span className="text-xs text-muted-foreground">({r.payments_count})</span></TableCell>
                <TableCell className="text-right tabular-nums">{m(r.sales_total)} <span className="text-xs text-muted-foreground">({r.sales_count})</span></TableCell>
                <TableCell className="text-right font-medium tabular-nums text-foreground">{m(r.total)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="hover:bg-transparent">
              <TableCell className="font-semibold text-foreground">Total</TableCell>
              <TableCell className="text-right font-semibold tabular-nums">{m(summary.payments_total)}</TableCell>
              <TableCell className="text-right font-semibold tabular-nums">{m(summary.sales_total)}</TableCell>
              <TableCell className="text-right font-semibold tabular-nums text-gold">{m(summary.total)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      )}

      <dl className="grid gap-x-6 gap-y-1 rounded-lg border border-border bg-input/30 p-3 text-sm sm:grid-cols-2">
        <div className="flex justify-between"><dt className="text-muted-foreground">Fondo inicial</dt><dd className="tabular-nums">{m(openingFloat)}</dd></div>
        <div className="flex justify-between"><dt className="text-muted-foreground">+ Efectivo membresías</dt><dd className="tabular-nums">{m(summary.cash_payments_total)}</dd></div>
        <div className="flex justify-between"><dt className="text-muted-foreground">+ Efectivo tienda</dt><dd className="tabular-nums">{m(summary.cash_sales_total)}</dd></div>
        <div className="flex justify-between font-semibold"><dt>= Efectivo esperado</dt><dd className="tabular-nums text-gold">{m(summary.expected_cash)}</dd></div>
        {summary.sales_count > 0 && (
          <div className="flex justify-between sm:col-span-2"><dt className="text-muted-foreground">IVA incluido en ventas de tienda</dt><dd className="tabular-nums">{m(summary.sales_tax_total)}</dd></div>
        )}
        {summary.voided_count > 0 && (
          <div className="flex justify-between text-destructive sm:col-span-2">
            <dt>Anulado en el turno ({summary.voided_count})</dt><dd className="tabular-nums">{m(summary.voided_total)}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
