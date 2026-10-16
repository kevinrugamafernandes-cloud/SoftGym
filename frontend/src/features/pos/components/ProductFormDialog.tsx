import { useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useProductCategories, useSaveProduct } from "@/hooks/useProducts";
import { toast } from "@/hooks/useToast";
import { getErrorCode, getFieldErrors } from "@/lib/axios";
import { describeInvalidFields } from "@/lib/form-errors";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { Product } from "@/types";
import { TAX_RATES, emptyProductForm, marginPct, productFormSchema, productToForm, toProductPayload, type ProductFormValues } from "../schemas";

export function ProductFormDialog({ product, open, onOpenChange }: { product?: Product; open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{product ? "Editar producto" : "Nuevo producto"}</DialogTitle>
          <DialogDescription>El precio de venta es el FINAL al cliente, con IVA incluido. El stock se mueve con entradas y ajustes.</DialogDescription>
        </DialogHeader>
        {open && <ProductForm product={product} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

const FIELDS = ["name", "sku", "category", "price", "cost", "tax_rate", "cabys_code", "min_stock", "initial_stock", "description"] as const;

function ProductForm({ product, onClose }: { product?: Product; onClose: () => void }) {
  const save = useSaveProduct();
  const categories = useProductCategories();
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, setError, watch, formState: { errors, isSubmitting } } = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: product ? productToForm(product) : emptyProductForm,
  });

  const [price, cost, rate] = watch(["price", "cost", "tax_rate"]);
  const margin = isDecimal(price ?? "") && isDecimal(cost ?? "")
    ? marginPct({ price: normalizeDecimal(price), cost: normalizeDecimal(cost), tax_rate: rate }) : null;
  const base = isDecimal(price ?? "") ? Number(normalizeDecimal(price)) / (1 + Number(rate) / 100) : null;

  const onSubmit = async (v: ProductFormValues) => {
    setFormError(null);
    try {
      const saved = await save.mutateAsync({ id: product?.id, payload: toProductPayload(v, !product) });
      toast({ variant: "success", title: product ? "Producto actualizado" : "Producto creado", description: saved.name });
      onClose();
    } catch (err) {
      setFormError(reportError(err, "No se pudo guardar el producto"));
      const code = getErrorCode(err);
      if (code === "product_name_taken") setError("name", { type: "server", message: "Ya existe un producto con este nombre" });
      if (code === "product_sku_taken") setError("sku", { type: "server", message: "Código en uso" });
      for (const fe of getFieldErrors(err)) {
        if ((FIELDS as readonly string[]).includes(fe.field)) setError(fe.field as keyof ProductFormValues, { type: "server", message: fe.message });
      }
    }
  };

  const err = (k: keyof ProductFormValues) => errors[k]?.message;
  const inv = (k: keyof ProductFormValues) => (errors[k] ? "border-destructive focus-visible:ring-destructive" : undefined);

  return (
    <form onSubmit={handleSubmit(onSubmit, (f: FieldErrors<ProductFormValues>) => setFormError(describeInvalidFields(f)))} noValidate className="space-y-4">
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="p-name">Nombre</Label>
          <Input id="p-name" autoComplete="off" autoFocus className={inv("name")} {...register("name")} />
          {err("name") && <p className="text-xs text-destructive">{err("name")}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-category">Categoría</Label>
          <Input id="p-category" list="p-categories" autoComplete="off" placeholder="Bebidas, Suplementos…" className={inv("category")} {...register("category")} />
          <datalist id="p-categories">{categories.data?.map((c) => <option key={c} value={c} />)}</datalist>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-sku">Código / código de barras <span className="text-muted-foreground">(opcional)</span></Label>
          <Input id="p-sku" autoComplete="off" className={inv("sku")} {...register("sku")} />
          {err("sku") && <p className="text-xs text-destructive">{err("sku")}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-price">Precio de venta con IVA (₡)</Label>
          <Input id="p-price" inputMode="decimal" autoComplete="off" className={cn("tabular-nums", inv("price"))} {...register("price")} />
          {err("price") ? <p className="text-xs text-destructive">{err("price")}</p>
            : base !== null && Number(rate) > 0 && <p className="text-xs text-muted-foreground">Base sin IVA: {formatMoney(base)} · IVA: {formatMoney(Number(normalizeDecimal(price)) - base)}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-tax">Tarifa de IVA</Label>
          <Select id="p-tax" {...register("tax_rate")}>
            {TAX_RATES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-cost">Costo unitario (₡) <span className="text-muted-foreground">(opcional)</span></Label>
          <Input id="p-cost" inputMode="decimal" autoComplete="off" className={cn("tabular-nums", inv("cost"))} {...register("cost")} />
          {err("cost") ? <p className="text-xs text-destructive">{err("cost")}</p>
            : margin !== null && <p className={cn("text-xs", margin < 0 ? "text-destructive" : "text-muted-foreground")}>Margen bruto: {margin.toFixed(1)} %</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-cabys">Código CABYS <span className="text-muted-foreground">(para factura electrónica)</span></Label>
          <Input id="p-cabys" inputMode="numeric" autoComplete="off" maxLength={13} className={cn("tabular-nums", inv("cabys_code"))} {...register("cabys_code")} />
          {err("cabys_code") && <p className="text-xs text-destructive">{err("cabys_code")}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-min">Stock mínimo (alerta)</Label>
          <Input id="p-min" inputMode="numeric" autoComplete="off" className={cn("tabular-nums", inv("min_stock"))} {...register("min_stock")} />
          {err("min_stock") && <p className="text-xs text-destructive">{err("min_stock")}</p>}
        </div>
        {!product && (
          <div className="space-y-1.5">
            <Label htmlFor="p-initial">Stock inicial</Label>
            <Input id="p-initial" inputMode="numeric" autoComplete="off" className={cn("tabular-nums", inv("initial_stock"))} {...register("initial_stock")} />
            {err("initial_stock") && <p className="text-xs text-destructive">{err("initial_stock")}</p>}
          </div>
        )}
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="p-desc">Descripción <span className="text-muted-foreground">(opcional)</span></Label>
          <Textarea id="p-desc" rows={2} {...register("description")} />
        </div>
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={isSubmitting}>{product ? "Guardar cambios" : "Crear producto"}</Button>
      </DialogFooter>
    </form>
  );
}
