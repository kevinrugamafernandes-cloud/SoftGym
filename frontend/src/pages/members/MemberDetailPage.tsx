import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, RefreshCw, UserX, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { usePermissions } from "@/features/auth";
import { MemberFormDialog } from "@/features/members/components/MemberFormDialog";
import { MemberStatusBadge } from "@/features/members/components/MemberStatusBadge";
import { MeasurementsPanel } from "@/features/measurements/components/MeasurementsPanel";
import { MemberBillingPanel } from "@/features/payments/components/MemberBillingPanel";
import { useDeleteMember, useMember } from "@/hooks/useMembers";
import { toast } from "@/hooks/useToast";
import { getErrorMessage, getErrorStatus } from "@/lib/axios";
import { GENDER_LABELS } from "@/lib/labels";
import { reportError } from "@/lib/report-error";
import { formatDate, formatPhone } from "@/utils";
import type { Member } from "@/types";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-foreground">{children}</dd>
    </div>
  );
}

function MemberInfo({ member }: { member: Member }) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-base">Datos del socio</CardTitle></CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Cédula"><span className="tabular-nums">{member.identification}</span></Field>
          <Field label="Teléfono"><span className="tabular-nums">{formatPhone(member.phone)}</span></Field>
          <Field label="Correo electrónico">{member.email ?? "—"}</Field>
          <Field label="Fecha de nacimiento">{formatDate(member.birth_date)}</Field>
          <Field label="Género">{member.gender ? GENDER_LABELS[member.gender] : "—"}</Field>
          <Field label="Fecha de ingreso">{formatDate(member.joined_at)}</Field>
          {member.notes && (
            <div className="sm:col-span-2 lg:col-span-3">
              <Field label="Notas internas"><span className="whitespace-pre-line">{member.notes}</span></Field>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

export function MemberDetailPage() {
  const { memberId } = useParams();
  const navigate = useNavigate();
  const { can } = usePermissions();
  const member = useMember(memberId);
  const deleteMember = useDeleteMember();

  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const back = (
    <Link to="/members" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
      <ArrowLeft className="h-4 w-4" aria-hidden /> Volver a socios
    </Link>
  );

  if (member.isLoading) {
    return (
      <div className="space-y-5" aria-busy="true" aria-label="Cargando socio">
        {back}
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (member.isError || !member.data) {
    const notFound = getErrorStatus(member.error) === 404;
    return (
      <div className="space-y-5">
        {back}
        {notFound ? (
          <EmptyState icon={Users} title="Socio no encontrado"
            description="El socio no existe o fue dado de baja."
            action={<Button asChild variant="gold"><Link to="/members">Ir al listado</Link></Button>} />
        ) : (
          <div className="space-y-3">
            <ErrorMessage title="No se pudo cargar al socio" message={getErrorMessage(member.error)} />
            <Button variant="outline" size="sm" onClick={() => void member.refetch()}>
              <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar
            </Button>
          </div>
        )}
      </div>
    );
  }

  const data = member.data;

  const confirmDelete = async () => {
    setDeleteError(null);
    try {
      await deleteMember.mutateAsync(data.id);
      toast({ variant: "success", title: "Socio dado de baja", description: `${data.full_name} fue dado de baja. Su historial se conserva.` });
      navigate("/members");
    } catch (err) {
      setDeleteError(reportError(err, "No se pudo dar de baja al socio"));
    }
  };

  return (
    <div className="space-y-5">
      {back}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold text-foreground">{data.full_name}</h2>
            <MemberStatusBadge status={data.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Socio desde el {formatDate(data.joined_at, { year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          {can("members.edit") && (
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="mr-2 h-4 w-4" aria-hidden /> Editar
            </Button>
          )}
          {can("members.delete") && (
            <Button variant="outline" className="text-destructive hover:text-destructive"
              onClick={() => { setDeleteError(null); setDeleting(true); }}>
              <UserX className="mr-2 h-4 w-4" aria-hidden /> Dar de baja
            </Button>
          )}
        </div>
      </div>

      <MemberInfo member={data} />

      {can("payments.view") && <MemberBillingPanel member={data} />}

      {can("measurements.view") && <MeasurementsPanel member={data} />}

      {editing && <MemberFormDialog open onOpenChange={(open) => !open && setEditing(false)} mode="edit" member={data} />}

      <ConfirmDialog
        open={deleting}
        onOpenChange={(open) => { if (!open) { setDeleting(false); setDeleteError(null); } }}
        title="Dar de baja al socio"
        description={
          <>
            ¿Dar de baja a <strong className="text-foreground">{data.full_name}</strong>? Dejará de aparecer en el
            listado, pero su historial se conserva y un administrador puede restaurarlo.
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
