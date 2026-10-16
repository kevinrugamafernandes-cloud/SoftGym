import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Pagination } from "@/components/common/Pagination";
import { usePermissions } from "@/features/auth";
import { MemberFormDialog } from "@/features/members/components/MemberFormDialog";
import { MembersList } from "@/features/members/components/MembersList";
import { MembersToolbar } from "@/features/members/components/MembersToolbar";
import { RestoreMemberDialog } from "@/features/members/components/RestoreMemberDialog";
import { MeasurementFormDialog } from "@/features/measurements/components/MeasurementFormDialog";
import { useDeleteMember, useMembers } from "@/hooks/useMembers";
import { useDebounce } from "@/hooks/useDebounce";
import { toast } from "@/hooks/useToast";
import { reportError } from "@/lib/report-error";
import type { Member, MemberFilters, MemberStatus } from "@/types";

const PAGE_SIZE = 10;
const VALID_STATUS: MemberStatus[] = ["activo", "inactivo", "por_vencer", "moroso"];

export function MembersPage() {
  const { can } = usePermissions();
  const [params, setParams] = useSearchParams();

  // Búsqueda, estado y página viven en la URL: recargar o volver con "atrás" los conserva.
  const urlSearch = params.get("q") ?? "";
  const rawStatus = params.get("estado") ?? "";
  const status = (VALID_STATUS.includes(rawStatus as MemberStatus) ? rawStatus : "") as MemberStatus | "";
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);

  const updateParams = useCallback(
    (next: { q?: string; estado?: string; pagina?: number }) => {
      setParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          const apply = (key: string, value: string | number | undefined) => {
            if (value === undefined || value === "" || value === 1) p.delete(key);
            else p.set(key, String(value));
          };
          if ("q" in next) apply("q", next.q);
          if ("estado" in next) apply("estado", next.estado);
          if ("pagina" in next) apply("pagina", next.pagina);
          return p;
        },
        { replace: true }
      );
    },
    [setParams]
  );

  // Buscador en tiempo real: se escribe sin demora y se consulta tras una pausa de 350 ms.
  const [searchText, setSearchText] = useState(urlSearch);
  const debouncedSearch = useDebounce(searchText, 350);
  const pushedSearch = useRef(urlSearch);

  useEffect(() => {
    const next = debouncedSearch.trim();
    if (next !== pushedSearch.current) {
      pushedSearch.current = next;
      updateParams({ q: next, pagina: 1 });
    }
  }, [debouncedSearch, updateParams]);

  useEffect(() => {
    // Cambio externo de la URL (botón "atrás"): sincroniza el cuadro de búsqueda.
    if (urlSearch !== pushedSearch.current) {
      pushedSearch.current = urlSearch;
      setSearchText(urlSearch);
    }
  }, [urlSearch]);

  const filters: MemberFilters = { search: urlSearch, status, page, size: PAGE_SIZE };
  const members = useMembers(filters);
  const data = members.data;

  // Si la página quedó fuera de rango (p. ej. tras dar de baja al último de la página), se corrige.
  useEffect(() => {
    if (!data) return;
    if (data.pages > 0 && page > data.pages) updateParams({ pagina: data.pages });
  }, [data, page, updateParams]);

  // ── Diálogos ───────────────────────────────────────────────────────────────
  const [formState, setFormState] = useState<{ mode: "create" } | { mode: "edit"; member: Member } | null>(null);

  // Acceso directo del panel principal: /members?nuevo=1 abre la inscripción.
  useEffect(() => {
    if (params.get("nuevo") === "1" && can("members.create")) {
      setFormState({ mode: "create" });
      setParams((prev) => { const p = new URLSearchParams(prev); p.delete("nuevo"); return p; }, { replace: true });
    }
  }, [params, setParams, can]);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [measureTarget, setMeasureTarget] = useState<Member | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Member | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteMember = useDeleteMember();

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteError(null);
    try {
      await deleteMember.mutateAsync(deleteTarget.id);
      toast({
        variant: "success",
        title: "Socio dado de baja",
        description: `${deleteTarget.full_name} fue dado de baja. Su historial se conserva y puede restaurarse.`,
      });
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(reportError(err, "No se pudo dar de baja al socio"));
    }
  };

  const hasFilters = urlSearch.trim() !== "" || status !== "";
  const searching = searchText.trim() !== urlSearch.trim() || (members.isFetching && !members.isLoading);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Socios</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Inscriba (con su primer cobro), consulte y administre a los socios.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-5 p-4 sm:p-6">
          <MembersToolbar
            searchText={searchText}
            onSearchText={setSearchText}
            status={status}
            onStatus={(value) => updateParams({ estado: value, pagina: 1 })}
            searching={searching}
            canCreate={can("members.create")}
            onCreate={() => setFormState({ mode: "create" })}
            canRestore={can("members.restore")}
            onRestore={() => setRestoreOpen(true)}
          />

          <MembersList
            members={data?.items}
            loading={members.isLoading}
            error={members.error}
            onRetry={() => void members.refetch()}
            hasFilters={hasFilters}
            canCreate={can("members.create")}
            onCreate={() => setFormState({ mode: "create" })}
            canEdit={can("members.edit")}
            canDelete={can("members.delete")}
            canMeasure={can("measurements.create")}
            onEdit={(member) => setFormState({ mode: "edit", member })}
            onDelete={(member) => { setDeleteError(null); setDeleteTarget(member); }}
            onMeasure={setMeasureTarget}
          />

          {data && (
            <Pagination
              page={data.page} pages={data.pages} total={data.total} size={data.size}
              onPageChange={(p) => updateParams({ pagina: p })}
              disabled={members.isFetching}
            />
          )}
        </CardContent>
      </Card>

      {formState && (
        <MemberFormDialog
          open
          onOpenChange={(open) => !open && setFormState(null)}
          mode={formState.mode}
          member={formState.mode === "edit" ? formState.member : undefined}
        />
      )}

      <RestoreMemberDialog open={restoreOpen} onOpenChange={setRestoreOpen} />

      {measureTarget && (
        <MeasurementFormDialog
          open
          onOpenChange={(open) => !open && setMeasureTarget(null)}
          memberId={measureTarget.id}
          memberName={measureTarget.full_name}
          mode="create"
        />
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) { setDeleteTarget(null); setDeleteError(null); } }}
        title="Dar de baja al socio"
        description={
          <>
            ¿Dar de baja a <strong className="text-foreground">{deleteTarget?.full_name}</strong>? Dejará de aparecer
            en el listado, pero su historial de pagos y mediciones se conserva y un administrador puede restaurarlo.
          </>
        }
        confirmLabel="Dar de baja"
        destructive
        loading={deleteMember.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
