import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Minus, Package, Plus, RefreshCw, Search, ShoppingCart, Trash2 } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { usePermissions } from "@/features/auth";
import { NoCashSessionAlert } from "@/features/cash/components/CashSessionIndicator";
import { MemberPicker } from "@/features/payments/components/MemberPicker";
import { PAYMENT_METHODS } from "@/features/payments/schemas";
import { PosNav } from "@/features/pos/components/PosNav";
import { SaleReceipt } from "@/features/pos/components/SaleReceipt";
import { MAX_QTY, cartReducer, cartTotals, overStock } from "@/features/pos/cart";
import { useCurrentCashSession } from "@/hooks/useCashSessions";
import { useDebounce } from "@/hooks/useDebounce";
import { useGymCurrency } from "@/hooks/usePayments";
import { useProductCategories, useProducts } from "@/hooks/useProducts";
import { useCreateSale } from "@/hooks/useSales";
import { toast } from "@/hooks/useToast";
import { getErrorCode, getErrorMessage } from "@/lib/axios";
import { PAYMENT_METHOD_LABELS, REFERENCE_REQUIRED_METHODS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { Member, PaymentMethod, Product, Sale } from "@/types";

type CustomerMode = "ninguno" | "socio" | "otro";

export function PosPage() {
  const { can } = usePermissions();
  const currency = useGymCurrency();
  const cash = useCurrentCashSession();
  const noCash = cash.isSuccess && cash.data === null;

  // ── Catálogo ───────────────────────────────────────────────────────────────
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const debounced = useDebounce(search, 250);
  const products = useProducts({ search: debounced, category, active_only: true, low_stock: false, page: 1, size: 200 });
  const categories = useProductCategories();
  const searchRef = useRef<HTMLInputElement>(null);

  // ── Carrito y cobro ────────────────────────────────────────────────────────
  const [cart, dispatch] = useReducer(cartReducer, []);
  const totals = cartTotals(cart);
  const tooMuch = overStock(cart);
  const [method, setMethod] = useState<PaymentMethod>("efectivo");
  const [reference, setReference] = useState("");
  const [received, setReceived] = useState("");
  const [customerMode, setCustomerMode] = useState<CustomerMode>("ninguno");
  const [member, setMember] = useState<Member | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ sale: Sale; change: number | null } | null>(null);
  const createSale = useCreateSale();

  // El stock que muestra el carrito se mantiene al día con cada recarga del catálogo.
  useEffect(() => {
    if (products.data) dispatch({ type: "refresh", products: products.data.items });
  }, [products.data]);

  const receivedNumber = received.trim() !== "" && isDecimal(received) ? Number(normalizeDecimal(received)) : null;
  const change = method === "efectivo" && receivedNumber !== null ? Math.round((receivedNumber - totals.total) * 100) / 100 : null;

  const add = (p: Product) => {
    if (p.stock <= 0) {
      toast({ variant: "destructive", title: "Sin stock", description: `${p.name} está agotado.` });
      return;
    }
    const inCart = cart.find((l) => l.product.id === p.id)?.quantity ?? 0;
    if (inCart >= p.stock) {
      toast({ variant: "destructive", title: "Stock insuficiente", description: `Solo hay ${p.stock} de ${p.name}.` });
      return;
    }
    dispatch({ type: "add", product: p });
    setError(null);
  };

  // Lector de código de barras / Enter: agrega el producto con ese código exacto o el único resultado.
  const onSearchEnter = () => {
    const items = products.data?.items ?? [];
    const q = search.trim().toLowerCase();
    const exact = items.find((p) => p.sku && p.sku.toLowerCase() === q);
    const pick = exact ?? (items.length === 1 ? items[0] : undefined);
    if (pick && debounced.trim().toLowerCase() === q) {
      add(pick);
      setSearch("");
    }
  };

  const reset = () => {
    dispatch({ type: "clear" });
    setMethod("efectivo"); setReference(""); setReceived("");
    setCustomerMode("ninguno"); setMember(null); setCustomerName(""); setCustomerPhone("");
    setError(null);
    searchRef.current?.focus();
  };

  const checkout = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (cart.length === 0) return setError("Agregue al menos un producto.");
    if (tooMuch.length) return setError(`Stock insuficiente: ${tooMuch.map((l) => `${l.product.name} (hay ${l.product.stock})`).join(", ")}.`);
    if (REFERENCE_REQUIRED_METHODS.has(method) && !reference.trim()) return setError(`Para ${PAYMENT_METHOD_LABELS[method]} indique el número de referencia.`);
    if (customerMode === "socio" && !member) return setError("Seleccione el socio o elija «Sin cliente».");
    if (customerMode === "otro" && customerPhone.trim() && customerPhone.replace(/\D/g, "").length < 8) return setError("El teléfono del cliente no es válido.");
    if (method === "efectivo" && change !== null && change < 0) return setError("El efectivo recibido es menor que el total.");

    try {
      const sale = await createSale.mutateAsync({
        items: cart.map((l) => ({ product_id: l.product.id, quantity: l.quantity })),
        method,
        reference: reference.trim() || null,
        member_id: customerMode === "socio" ? member?.id ?? null : null,
        customer_name: customerMode === "otro" ? customerName.trim() || null : null,
        customer_phone: customerMode === "otro" ? customerPhone.trim() || null : null,
      });
      toast({ variant: "success", title: `Venta ${sale.sale_code} registrada`, description: `Total ${formatMoney(sale.total, currency)}.` });
      setDone({ sale, change });
      reset();
    } catch (err) {
      setError(reportError(err, "No se pudo registrar la venta"));
      const code = getErrorCode(err);
      if (code === "insufficient_stock" || code === "product_inactive") void products.refetch();
      if (code === "cash_session_required") void cash.refetch();
    }
  };

  const catalog = products.data?.items ?? [];
  const cats = useMemo(() => categories.data ?? [], [categories.data]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Tienda</h2>
          <p className="mt-1 text-sm text-muted-foreground">Venda bebidas, suplementos y snacks. Las ventas suman a su caja abierta.</p>
        </div>
      </div>
      <PosNav />
      {noCash && <NoCashSessionAlert action="vender" />}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        {/* ── Catálogo ── */}
        <Card>
          <CardContent className="space-y-4 p-4 sm:p-5">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden />
              <Input ref={searchRef} autoFocus autoComplete="off" value={search} placeholder="Buscar por nombre o escanear código…"
                className="pl-9" aria-label="Buscar producto"
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onSearchEnter(); } }} />
            </div>
            {cats.length > 0 && (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Categorías">
                <Button size="sm" variant={category === "" ? "gold" : "outline"} onClick={() => setCategory("")}>Todas</Button>
                {cats.map((c) => (
                  <Button key={c} size="sm" variant={category === c ? "gold" : "outline"} onClick={() => setCategory(c)}>{c}</Button>
                ))}
              </div>
            )}

            {products.isLoading ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
              </div>
            ) : products.isError ? (
              <div className="space-y-3">
                <ErrorMessage title="No se pudo cargar el catálogo" message={getErrorMessage(products.error)} />
                <Button variant="outline" size="sm" onClick={() => void products.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
              </div>
            ) : catalog.length === 0 ? (
              <EmptyState icon={Package} title={debounced || category ? "Sin resultados" : "Aún no hay productos"}
                description={debounced || category ? "Pruebe con otro nombre o categoría." : "Un administrador debe cargarlos en Inventario."}
                action={!debounced && !category && can("products.manage")
                  ? <Button asChild variant="gold"><Link to="/tienda/inventario">Ir a inventario</Link></Button> : undefined} />
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {catalog.map((p) => {
                  const inCart = cart.find((l) => l.product.id === p.id)?.quantity ?? 0;
                  const out = p.stock <= 0;
                  return (
                    <button key={p.id} type="button" onClick={() => add(p)} disabled={out}
                      className={cn(
                        "relative flex min-h-28 flex-col justify-between rounded-lg border border-border bg-input/30 p-3 text-left transition-colors",
                        "hover:border-gold/50 hover:bg-gold/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        out && "cursor-not-allowed opacity-50 hover:border-border hover:bg-input/30",
                        inCart > 0 && "border-gold/60 bg-gold/5"
                      )}
                      aria-label={`Agregar ${p.name}, ${formatMoney(p.price, currency)}, ${p.stock} en stock`}>
                      {inCart > 0 && (
                        <span className="absolute right-2 top-2 flex h-6 min-w-6 items-center justify-center rounded-full bg-gold px-1.5 text-xs font-bold text-background">{inCart}</span>
                      )}
                      <div className="pr-6">
                        <p className="line-clamp-2 text-sm font-medium text-foreground">{p.name}</p>
                        {p.category && <p className="text-xs text-muted-foreground">{p.category}</p>}
                      </div>
                      <div className="mt-2 flex flex-wrap items-end justify-between gap-x-2">
                        <span className="font-semibold tabular-nums text-gold">{formatMoney(p.price, currency)}</span>
                        <span className={cn("text-xs tabular-nums", out ? "text-destructive" : p.low_stock ? "text-warning" : "text-muted-foreground")}>
                          {out ? "Agotado" : `${p.stock} disp.`}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Carrito y cobro ── */}
        <Card className="lg:sticky lg:top-0 lg:self-start">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShoppingCart className="h-4 w-4 text-gold" aria-hidden /> Venta actual
              {totals.items > 0 && <Badge variant="gold">{totals.items}</Badge>}
            </CardTitle>
            {cart.length > 0 && (
              <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => dispatch({ type: "clear" })}>Vaciar</Button>
            )}
          </CardHeader>
          <CardContent>
            <form onSubmit={checkout} noValidate className="space-y-4">
              {cart.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Toque un producto para agregarlo.
                </p>
              ) : (
                <ul className="max-h-72 divide-y divide-border/60 overflow-y-auto pr-1">
                  {cart.map((l) => {
                    const over = l.quantity > l.product.stock;
                    return (
                      <li key={l.product.id} className="space-y-1.5 py-2.5">
                        <div className="flex items-start justify-between gap-2">
                          <p className="min-w-0 text-sm font-medium text-foreground">{l.product.name}</p>
                          <Button type="button" variant="ghost" size="icon" className="-mr-2 -mt-1 h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                            aria-label={`Eliminar ${l.product.name}`} onClick={() => dispatch({ type: "remove", productId: l.product.id })}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1">
                            <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label={`Quitar uno de ${l.product.name}`}
                              onClick={() => dispatch({ type: "set", productId: l.product.id, quantity: l.quantity - 1 })}>
                              <Minus className="h-3.5 w-3.5" />
                            </Button>
                            <Input aria-label={`Cantidad de ${l.product.name}`} inputMode="numeric" value={l.quantity}
                              className={cn("h-8 w-12 px-1 text-center tabular-nums", over && "border-destructive")}
                              onChange={(e) => {
                                const n = Number.parseInt(e.target.value.replace(/\D/g, ""), 10);
                                dispatch({ type: "set", productId: l.product.id, quantity: Number.isNaN(n) ? 1 : Math.min(n, MAX_QTY) });
                              }} />
                            <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label={`Agregar uno de ${l.product.name}`}
                              onClick={() => add(l.product)}>
                              <Plus className="h-3.5 w-3.5" />
                            </Button>
                            <span className={cn("ml-1 text-xs tabular-nums", over ? "text-destructive" : "text-muted-foreground")}>
                              × {formatMoney(l.product.price, currency)}{over ? ` · solo hay ${l.product.stock}` : ""}
                            </span>
                          </div>
                          <span className="text-sm font-medium tabular-nums">{formatMoney(Number(l.product.price) * l.quantity, currency)}</span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              <dl className="space-y-1 border-t border-border pt-3 text-sm">
                <div className="flex justify-between text-muted-foreground"><dt>Subtotal sin IVA</dt><dd className="tabular-nums">{formatMoney(totals.subtotal, currency)}</dd></div>
                <div className="flex justify-between text-muted-foreground"><dt>IVA incluido</dt><dd className="tabular-nums">{formatMoney(totals.tax, currency)}</dd></div>
                <div className="flex justify-between text-lg font-bold"><dt>Total</dt><dd className="tabular-nums text-gold">{formatMoney(totals.total, currency)}</dd></div>
              </dl>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="pos-method">Método de pago</Label>
                  <Select id="pos-method" value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
                    {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>)}
                  </Select>
                </div>
                {method === "efectivo" ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="pos-received">Recibido <span className="text-muted-foreground">(opcional)</span></Label>
                    <Input id="pos-received" inputMode="decimal" autoComplete="off" placeholder="0" value={received}
                      className="tabular-nums" onChange={(e) => setReceived(e.target.value)} />
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label htmlFor="pos-ref">Referencia {REFERENCE_REQUIRED_METHODS.has(method) && <span className="text-destructive">*</span>}</Label>
                    <Input id="pos-ref" autoComplete="off" value={reference} maxLength={100}
                      placeholder={method === "sinpe" ? "N.º comprobante SINPE" : "N.º de autorización"} onChange={(e) => setReference(e.target.value)} />
                  </div>
                )}
              </div>
              {change !== null && (
                <p className={cn("rounded-md px-3 py-2 text-sm font-semibold tabular-nums", change >= 0 ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive")}>
                  {change >= 0 ? `Vuelto: ${formatMoney(change, currency)}` : `Faltan ${formatMoney(-change, currency)}`}
                </p>
              )}

              {/* Cliente (para el comprobante por WhatsApp) */}
              <div className="space-y-2">
                <Label>Cliente <span className="text-muted-foreground">(opcional)</span></Label>
                <div className="flex gap-1" role="group" aria-label="Tipo de cliente">
                  {(["ninguno", "socio", "otro"] as CustomerMode[]).map((mode) => (
                    <Button key={mode} type="button" size="sm" variant={customerMode === mode ? "gold" : "outline"} onClick={() => setCustomerMode(mode)}>
                      {mode === "ninguno" ? "Sin cliente" : mode === "socio" ? "Socio" : "Otro"}
                    </Button>
                  ))}
                </div>
                {customerMode === "socio" && <MemberPicker value={member} onChange={setMember} />}
                {customerMode === "otro" && (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                    <Input aria-label="Nombre del cliente" placeholder="Nombre" value={customerName} maxLength={160} onChange={(e) => setCustomerName(e.target.value)} />
                    <Input aria-label="Teléfono del cliente" type="tel" inputMode="tel" placeholder="WhatsApp 8888-1234" value={customerPhone} maxLength={20} onChange={(e) => setCustomerPhone(e.target.value)} />
                  </div>
                )}
              </div>

              {error && (
                <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
                  <AlertDescription className="text-foreground">{error}</AlertDescription>
                </Alert>
              )}

              <Button type="submit" variant="gold" size="lg" className="w-full" loading={createSale.isPending}
                disabled={cart.length === 0 || noCash}>
                Cobrar {formatMoney(totals.total, currency)}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Dialog open={done !== null} onOpenChange={(o) => !o && setDone(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Venta registrada</DialogTitle>
            <DialogDescription>El inventario se actualizó y la venta quedó en su caja.</DialogDescription>
          </DialogHeader>
          {done && <SaleReceipt sale={done.sale} currency={currency} change={done.change} />}
          <DialogFooter>
            <Button variant="gold" onClick={() => { setDone(null); searchRef.current?.focus(); }}>Nueva venta</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
