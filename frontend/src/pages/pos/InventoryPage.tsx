import { useState } from "react";
import { AlertTriangle, History, PackagePlus, Pencil, Plus, Power, RefreshCw, Package } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { usePermissions } from "@/features/auth";
import { PosNav } from "@/features/pos/components/PosNav";
import { ProductFormDialog } from "@/features/pos/components/ProductFormDialog";
import { MovementsDialog, StockDialog } from "@/features/pos/components/StockDialogs";
import { marginPct } from "@/features/pos/schemas";
import { useDebounce } from "@/hooks/useDebounce";
import { useGymCurrency } from "@/hooks/usePayments";
import { useProductCategories, useProducts, useToggleProduct } from "@/hooks/useProducts";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { formatMoney } from "@/lib/money";
import { cn } from "@/utils";
import type { Product } from "@/types";

export function InventoryPage() {
  const { can } = usePermissions();
  const manage = can("products.manage");
  const currency = useGymCurrency();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [view, setView] = useState<"activos" | "bajo" | "todos">("activos");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(search, 300);
  const products = useProducts({
    search: debounced, category, active_only: view === "activos", low_stock: view === "bajo", page, size: 25,
  });
  const categories = useProductCategories();
  const toggle = useToggleProduct();
  const data = products.data;

  const [editing, setEditing] = useState<Product | null | "new">(null);
  const [stockTarget, setStockTarget] = useState<Product | null>(null);
  const [history, setHistory] = useState<Product | null>(null);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Tienda</h2>
          <p className="mt-1 text-sm text-muted-foreground">Catálogo, precios con IVA y stock con bitácora de movimientos.</p>
        </div>
        {manage && (
          <Button variant="gold" onClick={() => setEditing("new")} className="shrink-0"><Plus className="mr-2 h-4 w-4" aria-hidden /> Nuevo producto</Button>
        )}
      </div>
      <PosNav />

      {data && data.low_stock_count > 0 && view !== "bajo" && (
        <button type="button" onClick={() => { setView("bajo"); setPage(1); }}
          className="flex w-full items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-left text-sm text-foreground hover:bg-warning/15">
          <AlertTriangle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
          {data.low_stock_count} {data.low_stock_count === 1 ? "producto está" : "productos están"} en o bajo el stock mínimo. Ver cuáles →
        </button>
      )}

      <Card>
        <CardContent className="space-y-5 p-4 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-[1fr_200px_200px]">
            <SearchInput value={search} onValueChange={(v) => { setSearch(v); setPage(1); }} aria-label="Buscar producto"
              loading={products.isFetching && !products.isLoading} placeholder="Buscar por nombre, código o categoría…" />
            <Select aria-label="Categoría" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
              <option value="">Todas las categorías</option>
              {categories.data?.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Select aria-label="Mostrar" value={view} onChange={(e) => { setView(e.target.value as typeof view); setPage(1); }}>
              <option value="activos">Activos</option>
              <option value="bajo">Stock bajo</option>
              <option value="todos">Todos (incluye inactivos)</option>
            </Select>
          </div>

          {products.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : products.isError ? (
            <div className="space-y-3">
              <ErrorMessage title="No se pudo cargar el inventario" message={getErrorMessage(products.error)} />
              <Button variant="outline" size="sm" onClick={() => void products.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState icon={Package} title={debounced || category || view !== "activos" ? "Sin resultados" : "Aún no hay productos"}
              description={debounced || category || view !== "activos" ? "Cambie los filtros." : "Cree el primer producto para empezar a vender."}
              action={manage && !debounced && !category && view === "activos"
                ? <Button variant="gold" onClick={() => setEditing("new")}><Plus className="mr-2 h-4 w-4" aria-hidden /> Nuevo producto</Button> : undefined} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Producto</TableHead>
                  <TableHead className="text-right">Precio</TableHead>
                  {manage && <TableHead className="hidden text-right md:table-cell">Costo / margen</TableHead>}
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="w-32"><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((p) => {
                  const margin = marginPct(p);
                  return (
                    <TableRow key={p.id} className={cn(!p.is_active && "opacity-60")}>
                      <TableCell>
                        <p className="font-medium text-foreground">{p.name} {!p.is_active && <Badge variant="outline" className="ml-1 text-muted-foreground">Inactivo</Badge>}</p>
                        <p className="text-xs text-muted-foreground">{[p.category, p.sku].filter(Boolean).join(" · ") || "—"}</p>
                      </TableCell>
                      <TableCell className="text-right">
                        <p className="font-medium tabular-nums">{formatMoney(p.price, currency)}</p>
                        <p className="text-xs text-muted-foreground">{Number(p.tax_rate) > 0 ? `IVA ${Number(p.tax_rate)} %` : "Exento"}</p>
                      </TableCell>
                      {manage && (
                        <TableCell className="hidden text-right md:table-cell">
                          <p className="tabular-nums">{p.cost ? formatMoney(p.cost, currency) : "—"}</p>
                          {margin !== null && <p className={cn("text-xs", margin < 0 ? "text-destructive" : "text-muted-foreground")}>{margin.toFixed(1)} %</p>}
                        </TableCell>
                      )}
                      <TableCell className="text-right">
                        <Badge variant={p.stock === 0 ? "destructive" : p.low_stock ? "warning" : "success"} className="tabular-nums">{p.stock}</Badge>
                        <p className="mt-0.5 text-xs text-muted-foreground">mín. {p.min_stock}</p>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-0.5">
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            onClick={() => setHistory(p)} aria-label={`Movimientos de ${p.name}`} title="Movimientos"><History className="h-4 w-4" /></Button>
                          {manage && (
                            <>
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={() => setStockTarget(p)} aria-label={`Entrada o ajuste de ${p.name}`} title="Entrada / ajuste"><PackagePlus className="h-4 w-4" /></Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={() => setEditing(p)} aria-label={`Editar ${p.name}`} title="Editar"><Pencil className="h-4 w-4" /></Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" disabled={toggle.isPending}
                                onClick={() => toggle.mutate({ id: p.id, is_active: !p.is_active }, {
                                  onSuccess: (r) => toast({ variant: "success", title: r.is_active ? "Producto activado" : "Producto desactivado", description: r.name }),
                                })}
                                aria-label={`${p.is_active ? "Desactivar" : "Activar"} ${p.name}`} title={p.is_active ? "Desactivar (no se vende)" : "Activar"}>
                                <Power className={cn("h-4 w-4", p.is_active ? "" : "text-success")} />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
          {data && <Pagination page={data.page} pages={data.pages} total={data.total} size={data.size} onPageChange={setPage} disabled={products.isFetching} />}
        </CardContent>
      </Card>

      <ProductFormDialog open={editing !== null} product={editing && editing !== "new" ? editing : undefined}
        onOpenChange={(o) => !o && setEditing(null)} />
      <StockDialog product={stockTarget} onOpenChange={(o) => !o && setStockTarget(null)} />
      <MovementsDialog product={history} onOpenChange={(o) => !o && setHistory(null)} />
    </div>
  );
}
