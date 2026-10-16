import { useEffect, useState } from "react";
import { Pencil, Plus, RefreshCw, Ruler, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { usePermissions } from "@/features/auth";
import { useDeleteMeasurement, useMeasurements } from "@/hooks/useMeasurements";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { formatNumber } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn, formatDate } from "@/utils";
import type { Measurement, Member } from "@/types";

import { BmiBadge } from "./BmiBadge";
import { MeasurementFormDialog } from "./MeasurementFormDialog";

const PAGE = 50;

/** Diferencia entre dos valores ya calculados por el servidor (solo resta; no calcula IMC). */
function delta(current: string | null, previous: string | null, unit: string, min = 0) {
  if (current === null || previous === null) return null;
  const diff = Number(current) - Number(previous);
  if (Number.isNaN(diff) || Math.abs(diff) < 0.005) return { text: `Sin cambio ${unit}`.trim(), tone: "text-muted-foreground" };
  const sign = diff > 0 ? "+" : "−";
  return {
    text: `${sign}${formatNumber(Math.abs(diff), { min, max: 2 })} ${unit}`.trim(),
    tone: "text-muted-foreground",
  };
}

function Stat({ label, value, hint, children }: { label: string; value: string; hint?: string | null; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-background/40 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}

export function MeasurementsPanel({ member }: { member: Member }) {
  const { can } = usePermissions();
  const [limit, setLimit] = useState(PAGE);
  const history = useMeasurements(member.id, limit);
  const remove = useDeleteMeasurement(member.id);

  const [form, setForm] = useState<{ mode: "create" } | { mode: "edit"; measurement: Measurement } | null>(null);
  const [toDelete, setToDelete] = useState<Measurement | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  useEffect(() => {
    if (!highlightId) return;
    const id = setTimeout(() => setHighlightId(null), 4000);
    return () => clearTimeout(id);
  }, [highlightId]);

  const items = history.data?.items ?? [];
  const total = history.data?.total ?? 0;
  const latest = items[0];
  const previous = items[1];
  const canCreate = can("measurements.create");
  const canEdit = can("measurements.edit");
  const canDelete = can("measurements.delete");
  const showActions = canEdit || canDelete;

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleteError(null);
    try {
      await remove.mutateAsync(toDelete.id);
      toast({ variant: "success", title: "Medición eliminada", description: "El registro se eliminó del historial." });
      setToDelete(null);
    } catch (err) {
      setDeleteError(reportError(err, "No se pudo eliminar la medición"));
    }
  };

  const weightDelta = latest && previous ? delta(latest.weight_kg, previous.weight_kg, "kg", 0) : null;
  const bmiDelta = latest && previous ? delta(latest.bmi, previous.bmi, "", 1) : null;

  return (
    <Card>
      <CardHeader className="flex flex-col items-start gap-3 space-y-0 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base">Ficha física</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">Evolución de peso, IMC y medidas corporales.</p>
        </div>
        {canCreate && (
          <Button variant="gold" size="sm" onClick={() => setForm({ mode: "create" })}>
            <Plus className="mr-2 h-4 w-4" aria-hidden /> Registrar medición
          </Button>
        )}
      </CardHeader>

      <CardContent className="space-y-5">
        {history.isLoading ? (
          <div className="space-y-3" aria-busy="true" aria-label="Cargando mediciones">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24" />)}
            </div>
            <Skeleton className="h-40" />
          </div>
        ) : history.isError && !history.data ? (
          <div className="space-y-3">
            <ErrorMessage title="No se pudo cargar la ficha física" message={getErrorMessage(history.error)} />
            <Button variant="outline" size="sm" onClick={() => void history.refetch()}>
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar
            </Button>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={Ruler}
            title="Sin mediciones registradas"
            description="Registre peso y estatura para empezar a seguir la evolución del socio."
            action={canCreate ? <Button variant="gold" onClick={() => setForm({ mode: "create" })}>Registrar medición</Button> : undefined}
          />
        ) : (
          <>
            {/* Resumen de la última medición (valores calculados por el servidor) */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="measurement-summary">
              <Stat label="Peso" value={`${formatNumber(latest.weight_kg)} kg`} hint={weightDelta ? `${weightDelta.text} vs. anterior` : null} />
              <Stat label="Estatura" value={`${formatNumber(latest.height_cm)} cm`} />
              <Stat label="IMC" value={formatNumber(latest.bmi, { min: 1 })} hint={bmiDelta ? `${bmiDelta.text} vs. anterior`.trim() : null}>
                <BmiBadge category={latest.bmi_category} />
              </Stat>
              <Stat label="Última medición" value={formatDate(latest.recorded_at)} hint={`${total} ${total === 1 ? "registro" : "registros"} en total`} />
            </div>

            {/* Historial: escritorio */}
            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Fecha</TableHead>
                    <TableHead>Peso</TableHead>
                    <TableHead>Estatura</TableHead>
                    <TableHead>IMC</TableHead>
                    <TableHead>Clasificación</TableHead>
                    <TableHead>% Grasa</TableHead>
                    <TableHead>% Músculo</TableHead>
                    <TableHead>Cintura</TableHead>
                    {showActions && <TableHead className="text-right">Acciones</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((m) => (
                    <TableRow key={m.id} className={cn(highlightId === m.id && "bg-gold/10")}>
                      <TableCell className="whitespace-nowrap">{formatDate(m.recorded_at)}</TableCell>
                      <TableCell className="tabular-nums">{formatNumber(m.weight_kg)} kg</TableCell>
                      <TableCell className="tabular-nums">{formatNumber(m.height_cm)} cm</TableCell>
                      <TableCell className="tabular-nums font-medium">{formatNumber(m.bmi, { min: 1 })}</TableCell>
                      <TableCell><BmiBadge category={m.bmi_category} /></TableCell>
                      <TableCell className="tabular-nums text-muted-foreground">{formatNumber(m.body_fat_pct)}</TableCell>
                      <TableCell className="tabular-nums text-muted-foreground">{formatNumber(m.muscle_pct)}</TableCell>
                      <TableCell className="tabular-nums text-muted-foreground">{formatNumber(m.waist_cm)}</TableCell>
                      {showActions && (
                        <TableCell>
                          <div className="flex justify-end gap-0.5">
                            {canEdit && (
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={() => setForm({ mode: "edit", measurement: m })}
                                aria-label={`Editar medición del ${formatDate(m.recorded_at)}`} title="Editar">
                                <Pencil className="h-4 w-4" />
                              </Button>
                            )}
                            {canDelete && (
                              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                onClick={() => { setDeleteError(null); setToDelete(m); }}
                                aria-label={`Eliminar medición del ${formatDate(m.recorded_at)}`} title="Eliminar">
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Historial: móvil */}
            <ul className="space-y-3 md:hidden">
              {items.map((m) => (
                <li key={m.id} className={cn("rounded-lg border border-border p-3", highlightId === m.id && "bg-gold/10")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{formatDate(m.recorded_at)}</span>
                    <BmiBadge category={m.bmi_category} />
                  </div>
                  <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div><dt className="text-muted-foreground">Peso</dt><dd className="tabular-nums">{formatNumber(m.weight_kg)} kg</dd></div>
                    <div><dt className="text-muted-foreground">Estatura</dt><dd className="tabular-nums">{formatNumber(m.height_cm)} cm</dd></div>
                    <div><dt className="text-muted-foreground">IMC</dt><dd className="tabular-nums font-medium">{formatNumber(m.bmi, { min: 1 })}</dd></div>
                  </dl>
                  {showActions && (
                    <div className="mt-2 flex justify-end gap-1 border-t border-border pt-2">
                      {canEdit && <Button variant="ghost" size="sm" onClick={() => setForm({ mode: "edit", measurement: m })}>Editar</Button>}
                      {canDelete && <Button variant="ghost" size="sm" className="text-destructive" onClick={() => { setDeleteError(null); setToDelete(m); }}>Eliminar</Button>}
                    </div>
                  )}
                </li>
              ))}
            </ul>

            {total > items.length && (
              <div className="flex justify-center">
                <Button variant="outline" size="sm" onClick={() => setLimit((l) => l + PAGE)} loading={history.isFetching}>
                  Ver más mediciones ({items.length} de {total})
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>

      {form && (
        <MeasurementFormDialog
          open
          onOpenChange={(open) => !open && setForm(null)}
          memberId={member.id}
          memberName={member.full_name}
          mode={form.mode}
          measurement={form.mode === "edit" ? form.measurement : undefined}
          defaultHeightCm={latest?.height_cm ?? null}
          onSaved={(m) => setHighlightId(m.id)}
        />
      )}

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => { if (!open) { setToDelete(null); setDeleteError(null); } }}
        title="Eliminar medición"
        description={`Se eliminará la medición del ${toDelete ? formatDate(toDelete.recorded_at) : ""}. Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        destructive
        loading={remove.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
      />
    </Card>
  );
}
