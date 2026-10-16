import { useState } from "react";
import { AlertCircle, ArrowDownToLine, ClipboardCheck } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Pagination } from "@/components/common/Pagination";
import { useChangeStock, useProductMovements } from "@/hooks/useProducts";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { MOVEMENT_KIND_LABELS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { Product } from "@/types";

/** Entrada de mercadería (suma) o ajuste por conteo físico (fija el stock, con motivo). */
export function StockDialog({ product, onOpenChange }: { product: Product | null; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={product !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        {product && <StockForm key={product.id} product={product} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function StockForm({ product, onClose }: { product: Product; onClose: () => void }) {
  const change = useChangeStock();
  const [kind, setKind] = useState<"entrada" | "ajuste">("entrada");
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const n = /^\d{1,6}$/.test(qty.trim()) ? Number(qty) : null;
  const resulting = n === null ? null : kind === "entrada" ? product.stock + n : n;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (n === null || (kind === "entrada" && n < 1)) return setError(kind === "entrada" ? "Indique cuántas unidades ingresan." : "Indique el stock contado (0 o más).");
    if (kind === "ajuste" && notes.trim().length < 3) return setError("Indique el motivo del ajuste.");
    if (kind === "ajuste" && n === product.stock) return setError("El stock contado es igual al actual: no hay nada que ajustar.");
    if (cost.trim() && !isDecimal(cost)) return setError("Costo inválido.");
    try {
      const p = await change.mutateAsync({
        id: product.id,
        payload: kind === "entrada"
          ? { kind, quantity: n, unit_cost: cost.trim() ? normalizeDecimal(cost) : null, notes: notes.trim() || null }
          : { kind, counted_stock: n, notes: notes.trim() },
      });
      toast({ variant: "success", title: "Inventario actualizado", description: `${p.name}: ${p.stock} unidades.` });
      onClose();
    } catch (err) {
      setError(reportError(err, "No se pudo actualizar el inventario"));
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <DialogHeader>
        <DialogTitle>Movimiento de inventario</DialogTitle>
        <DialogDescription>{product.name} · stock actual <strong className="text-foreground">{product.stock}</strong></DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-2 gap-2" role="group" aria-label="Tipo de movimiento">
        <Button type="button" variant={kind === "entrada" ? "gold" : "outline"} onClick={() => setKind("entrada")}>
          <ArrowDownToLine className="mr-2 h-4 w-4" aria-hidden /> Entrada
        </Button>
        <Button type="button" variant={kind === "ajuste" ? "gold" : "outline"} onClick={() => setKind("ajuste")}>
          <ClipboardCheck className="mr-2 h-4 w-4" aria-hidden /> Ajuste por conteo
        </Button>
      </div>
      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="st-qty">{kind === "entrada" ? "Unidades que ingresan" : "Stock contado"}</Label>
          <Input id="st-qty" inputMode="numeric" autoFocus autoComplete="off" value={qty} className="tabular-nums"
            onChange={(e) => setQty(e.target.value.replace(/\D/g, "").slice(0, 6))} />
        </div>
        {kind === "entrada" && (
          <div className="space-y-1.5">
            <Label htmlFor="st-cost">Costo unitario <span className="text-muted-foreground">(opcional)</span></Label>
            <Input id="st-cost" inputMode="decimal" autoComplete="off" value={cost} className="tabular-nums" onChange={(e) => setCost(e.target.value)} />
          </div>
        )}
      </div>
      {resulting !== null && (
        <p className="text-sm text-muted-foreground">Quedarán <strong className="tabular-nums text-foreground">{resulting}</strong> unidades
          {kind === "ajuste" && resulting !== product.stock && <> ({resulting > product.stock ? "+" : ""}{resulting - product.stock})</>}.</p>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="st-notes">{kind === "ajuste" ? "Motivo" : "Observaciones"} {kind === "ajuste" ? <span className="text-destructive">*</span> : <span className="text-muted-foreground">(opcional)</span>}</Label>
        <Input id="st-notes" autoComplete="off" maxLength={500} value={notes} placeholder={kind === "ajuste" ? "Ej.: 2 unidades vencidas" : "Ej.: factura del proveedor 1234"}
          onChange={(e) => setNotes(e.target.value)} />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={change.isPending}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={change.isPending}>Registrar</Button>
      </DialogFooter>
    </form>
  );
}

/** Bitácora de inventario de un producto. */
export function MovementsDialog({ product, onOpenChange }: { product: Product | null; onOpenChange: (o: boolean) => void }) {
  const [page, setPage] = useState(1);
  const movements = useProductMovements(product?.id ?? null, page);
  const data = movements.data;
  return (
    <Dialog open={product !== null} onOpenChange={(o) => { if (!o) setPage(1); onOpenChange(o); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Movimientos de inventario</DialogTitle>
          <DialogDescription>{product?.name} · stock actual {product?.stock}</DialogDescription>
        </DialogHeader>
        {movements.isLoading ? (
          <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : movements.isError ? (
          <p className="text-sm text-destructive">{getErrorMessage(movements.error)}</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Fecha</TableHead>
                  <TableHead>Movimiento</TableHead>
                  <TableHead className="text-right">Cant.</TableHead>
                  <TableHead className="text-right">Saldo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="whitespace-nowrap text-xs tabular-nums">{new Date(m.created_at).toLocaleString("es-CR", { dateStyle: "short", timeStyle: "short" })}</TableCell>
                    <TableCell>
                      <p className="text-sm text-foreground">{MOVEMENT_KIND_LABELS[m.kind]}{m.sale_code ? ` · ${m.sale_code}` : ""}</p>
                      <p className="text-xs text-muted-foreground">{[m.user_name, m.notes, m.unit_cost ? `costo ${formatMoney(m.unit_cost)}` : null].filter(Boolean).join(" · ")}</p>
                    </TableCell>
                    <TableCell className={cn("text-right font-medium tabular-nums", m.quantity > 0 ? "text-success" : "text-destructive")}>
                      {m.quantity > 0 ? `+${m.quantity}` : m.quantity}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{m.stock_after}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {data && <Pagination page={data.page} pages={data.pages} total={data.total} size={data.size} onPageChange={setPage} disabled={movements.isFetching} />}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
