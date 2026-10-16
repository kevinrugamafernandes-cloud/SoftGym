import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Copy, MessageCircle, PhoneOff, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { Pagination } from "@/components/common/Pagination";
import { SearchInput } from "@/components/common/SearchInput";
import { usePermissions } from "@/features/auth";
import { PaymentFormDialog } from "@/features/payments/components/PaymentFormDialog";
import { useCollections, useLogReminder } from "@/hooks/useAdmin";
import { useDebounce } from "@/hooks/useDebounce";
import { useMember } from "@/hooks/useMembers";
import { useGymCurrency } from "@/hooks/usePayments";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { cn, formatDate, formatPhone } from "@/utils";
import type { CollectionItem, CollectionState } from "@/types";

const PAGE_SIZE = 25;

function since(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  return days <= 0 ? "hoy" : days === 1 ? "ayer" : `hace ${days} días`;
}

export function CollectionsPage() {
  const { can } = usePermissions();
  const currency = useGymCurrency();
  const [params, setParams] = useSearchParams();
  const state: CollectionState = params.get("estado") === "por_vencer" ? "por_vencer" : "vencida";
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debounced = useDebounce(search, 300);
  useEffect(() => setPage(1), [debounced, state]);

  const list = useCollections({ state, search: debounced, page, size: PAGE_SIZE });
  const logReminder = useLogReminder();
  const data = list.data;
  const [chargeId, setChargeId] = useState<string | null>(null);
  const chargeMember = useMember(chargeId ?? undefined);

  const setState = (s: CollectionState) =>
    setParams((prev) => { const p = new URLSearchParams(prev); if (s === "vencida") p.delete("estado"); else p.set("estado", s); return p; }, { replace: true });

  const send = (item: CollectionItem) => {
    if (!item.whatsapp_url) return;
    window.open(item.whatsapp_url, "_blank", "noopener");
    logReminder.mutate({ memberId: item.member_id, kind: item.state });
  };

  const copy = async (item: CollectionItem) => {
    try {
      await navigator.clipboard.writeText(item.message);
      toast({ variant: "success", title: "Mensaje copiado", description: item.full_name });
    } catch {
      toast({ variant: "destructive", title: "No se pudo copiar el mensaje" });
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Morosos y vencimientos</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Recuerde el pago con un clic: se abre WhatsApp con el mensaje listo. Edite el texto en Configuración.
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Tipo de lista">
        {([["vencida", "Vencidas", data?.overdue_count], ["por_vencer", "Por vencer", data?.expiring_count]] as const).map(([key, label, count]) => (
          <Button key={key} role="tab" aria-selected={state === key} variant={state === key ? "gold" : "outline"} onClick={() => setState(key)}>
            {label}
            {count !== undefined && (
              <span className={cn("ml-2 rounded-full px-2 text-xs tabular-nums", state === key ? "bg-background/20" : "bg-muted")}>{count}</span>
            )}
          </Button>
        ))}
      </div>

      <Card>
        <CardContent className="space-y-5 p-4 sm:p-6">
          <SearchInput value={search} onValueChange={setSearch} placeholder="Buscar por nombre o cédula…" aria-label="Buscar socio"
            loading={list.isFetching && !list.isLoading} className="max-w-md" />

          {list.isLoading ? (
            <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
          ) : list.isError ? (
            <div className="space-y-3">
              <ErrorMessage title="No se pudo cargar la lista" message={getErrorMessage(list.error)} />
              <Button variant="outline" size="sm" onClick={() => void list.refetch()}><RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar</Button>
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState icon={CheckCircle2}
              title={debounced ? "Sin resultados" : state === "vencida" ? "No hay socios morosos" : "Ninguna membresía vence pronto"}
              description={debounced ? "Pruebe con otro nombre o cédula." : "¡Todo al día!"} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Socio</TableHead>
                  <TableHead className="hidden md:table-cell">Plan</TableHead>
                  <TableHead>{state === "vencida" ? "Venció" : "Vence"}</TableHead>
                  <TableHead className="hidden lg:table-cell">Último recordatorio</TableHead>
                  <TableHead className="w-48 text-right"><span className="sr-only">Acciones</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((i) => (
                  <TableRow key={i.member_id}>
                    <TableCell>
                      <Link to={`/members/${i.member_id}`} className="font-medium text-foreground hover:text-gold hover:underline">{i.full_name}</Link>
                      <p className="text-xs tabular-nums text-muted-foreground">{i.identification} · {formatPhone(i.phone)}</p>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{i.plan_name}</TableCell>
                    <TableCell>
                      <p className="tabular-nums">{formatDate(i.end_date)}</p>
                      <p className={cn("text-xs font-medium", i.state === "vencida" ? "text-destructive" : "text-warning")}>{i.label}</p>
                    </TableCell>
                    <TableCell className="hidden text-sm text-muted-foreground lg:table-cell">
                      {i.last_reminder_at ? since(i.last_reminder_at) : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        {i.whatsapp_url ? (
                          <Button size="sm" variant="outline" className="border-success/40 text-success hover:text-success"
                            onClick={() => send(i)} title={i.message} aria-label={`Enviar recordatorio por WhatsApp a ${i.full_name}`}>
                            <MessageCircle className="mr-1.5 h-4 w-4" aria-hidden /> WhatsApp
                          </Button>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 text-xs text-muted-foreground" title="Agregue el teléfono en la ficha del socio">
                            <PhoneOff className="h-3.5 w-3.5" aria-hidden /> Sin teléfono
                          </span>
                        )}
                        <Button size="icon" variant="ghost" className="h-9 w-9 text-muted-foreground hover:text-foreground"
                          onClick={() => void copy(i)} aria-label={`Copiar mensaje para ${i.full_name}`} title="Copiar mensaje">
                          <Copy className="h-4 w-4" />
                        </Button>
                        {can("payments.create") && (
                          <Button size="sm" variant="gold" onClick={() => setChargeId(i.member_id)}>Cobrar</Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {data && <Pagination page={data.page} pages={data.pages} total={data.total} size={data.size} onPageChange={setPage} disabled={list.isFetching} />}
        </CardContent>
      </Card>

      {chargeId && chargeMember.data && (
        <PaymentFormDialog open member={chargeMember.data} currency={currency} onOpenChange={(o) => !o && setChargeId(null)} />
      )}
    </div>
  );
}
