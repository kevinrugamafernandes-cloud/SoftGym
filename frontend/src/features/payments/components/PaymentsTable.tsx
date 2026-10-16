import { useState } from "react";
import { Link } from "react-router-dom";
import { Ban, FileText, Receipt, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { getErrorMessage } from "@/lib/axios";
import { PAYMENT_METHOD_LABELS } from "@/lib/labels";
import { formatMoney, isPositiveAmount } from "@/lib/money";
import { cn, formatDate } from "@/utils";
import type { Payment } from "@/types";
import { openReceiptPdf } from "../receipt";

interface PaymentsTableProps {
  payments: Payment[] | undefined;
  currency: string;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  canVoid: boolean;
  onVoid: (payment: Payment) => void;
  /** Oculta la columna de socio (p. ej. en la ficha del propio socio). */
  hideMember?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
}

export function PaymentsTable({
  payments, currency, loading, error, onRetry, canVoid, onVoid, hideMember,
  emptyTitle = "Sin pagos", emptyDescription = "No hay pagos que coincidan con los filtros.", emptyAction,
}: PaymentsTableProps) {
  const [opening, setOpening] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Cargando pagos">
        {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorMessage title="No se pudieron cargar los pagos" message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar
        </Button>
      </div>
    );
  }
  if (!payments || payments.length === 0) {
    return <EmptyState icon={Receipt} title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  }

  const pdf = async (p: Payment) => {
    setOpening(p.id);
    try { await openReceiptPdf(p.id, p.receipt_code); } finally { setOpening(null); }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Comprobante</TableHead>
          <TableHead>Fecha</TableHead>
          {!hideMember && <TableHead>Socio</TableHead>}
          <TableHead className="hidden md:table-cell">Plan y periodo</TableHead>
          <TableHead className="hidden sm:table-cell">Método</TableHead>
          <TableHead className="text-right">Monto</TableHead>
          <TableHead className="w-24 text-right"><span className="sr-only">Acciones</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {payments.map((p) => (
          <TableRow key={p.id} className={cn(p.is_voided && "opacity-60")}>
            <TableCell>
              <div className="flex flex-col gap-1">
                <span className="font-medium tabular-nums text-foreground">{p.receipt_code}</span>
                {p.is_voided && (
                  <Badge variant="destructive" className="w-fit"
                    title={`Anulado${p.voided_by_name ? ` por ${p.voided_by_name}` : ""}: ${p.void_reason ?? ""}`}>
                    Anulado
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="whitespace-nowrap tabular-nums">{formatDate(p.payment_date)}</TableCell>
            {!hideMember && (
              <TableCell>
                <Link to={`/members/${p.member.id}`} className="text-foreground hover:text-gold hover:underline">
                  {p.member.full_name}
                </Link>
                <p className="text-xs tabular-nums text-muted-foreground">{p.member.identification}</p>
              </TableCell>
            )}
            <TableCell className="hidden md:table-cell">
              <p className="text-foreground">{p.plan.name}</p>
              <p className="text-xs text-muted-foreground">{formatDate(p.period.start_date)} – {formatDate(p.period.end_date)}</p>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <p>{PAYMENT_METHOD_LABELS[p.method]}</p>
              {p.reference && <p className="max-w-[10rem] truncate text-xs text-muted-foreground" title={p.reference}>Ref. {p.reference}</p>}
            </TableCell>
            <TableCell className="text-right">
              <span className={cn("font-medium tabular-nums text-foreground", p.is_voided && "line-through")}>
                {formatMoney(p.amount, currency)}
              </span>
              {isPositiveAmount(p.discount) && !p.is_voided && (
                <p className="text-xs text-warning tabular-nums">−{formatMoney(p.discount, currency)}</p>
              )}
            </TableCell>
            <TableCell>
              <div className="flex items-center justify-end gap-0.5">
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                  disabled={opening === p.id} onClick={() => void pdf(p)}
                  aria-label={`Comprobante ${p.receipt_code}`} title="Ver comprobante PDF">
                  <FileText className={cn("h-4 w-4", opening === p.id && "animate-pulse")} />
                </Button>
                {canVoid && !p.is_voided && (
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={() => onVoid(p)} aria-label={`Anular ${p.receipt_code}`} title="Anular pago">
                    <Ban className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
