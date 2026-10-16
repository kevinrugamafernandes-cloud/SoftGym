import { Eye, Pencil, RefreshCw, Ruler, UserX, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { getErrorMessage } from "@/lib/axios";
import { formatDate, formatPhone } from "@/utils";
import type { Member } from "@/types";
import { MemberStatusBadge } from "./MemberStatusBadge";

export interface MemberRowActions {
  canEdit: boolean;
  canDelete: boolean;
  canMeasure: boolean;
  onEdit: (member: Member) => void;
  onDelete: (member: Member) => void;
  onMeasure: (member: Member) => void;
}

interface MembersListProps extends MemberRowActions {
  members: Member[] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  hasFilters: boolean;
  canCreate: boolean;
  onCreate: () => void;
}

function RowActions({ member, actions }: { member: Member; actions: MemberRowActions }) {
  const iconBtn = "h-8 w-8 text-muted-foreground hover:text-foreground";
  return (
    <div className="flex items-center justify-end gap-0.5">
      <Button asChild variant="ghost" size="icon" className={iconBtn}>
        <Link to={`/members/${member.id}`} aria-label={`Ver ficha de ${member.full_name}`} title="Ver ficha">
          <Eye className="h-4 w-4" />
        </Link>
      </Button>
      {actions.canEdit && (
        <Button variant="ghost" size="icon" className={iconBtn} onClick={() => actions.onEdit(member)}
          aria-label={`Editar a ${member.full_name}`} title="Editar">
          <Pencil className="h-4 w-4" />
        </Button>
      )}
      {actions.canMeasure && (
        <Button variant="ghost" size="icon" className={iconBtn} onClick={() => actions.onMeasure(member)}
          aria-label={`Registrar medidas de ${member.full_name}`} title="Registrar medidas">
          <Ruler className="h-4 w-4" />
        </Button>
      )}
      {actions.canDelete && (
        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={() => actions.onDelete(member)} aria-label={`Dar de baja a ${member.full_name}`} title="Dar de baja">
          <UserX className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}

export function MembersList({
  members, loading, error, onRetry, hasFilters, canCreate, onCreate, ...actions
}: MembersListProps) {
  if (loading) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Cargando socios">
        {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 w-full" />)}
      </div>
    );
  }

  if (error && !members) {
    return (
      <div className="space-y-3">
        <ErrorMessage title="No se pudo cargar el listado de socios" message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Reintentar
        </Button>
      </div>
    );
  }

  if (!members || members.length === 0) {
    return hasFilters ? (
      <EmptyState icon={Users} title="No se encontraron socios"
        description="Pruebe con otro nombre, cédula o estado." />
    ) : (
      <EmptyState icon={Users} title="Aún no hay socios registrados"
        description="Registre al primer socio de Lion Fitness Center para comenzar."
        action={canCreate ? <Button variant="gold" onClick={onCreate}>Inscribir socio</Button> : undefined} />
    );
  }

  return (
    <>
      {/* Escritorio: tabla */}
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Socio</TableHead>
              <TableHead>Cédula</TableHead>
              <TableHead>Teléfono</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Ingreso</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((m) => (
              <TableRow key={m.id}>
                <TableCell>
                  <Link to={`/members/${m.id}`} className="font-medium text-foreground hover:text-gold">
                    {m.full_name}
                  </Link>
                  {m.email && <p className="text-xs text-muted-foreground">{m.email}</p>}
                </TableCell>
                <TableCell className="tabular-nums text-muted-foreground">{m.identification}</TableCell>
                <TableCell className="tabular-nums text-muted-foreground">{formatPhone(m.phone)}</TableCell>
                <TableCell><MemberStatusBadge status={m.status} /></TableCell>
                <TableCell className="text-muted-foreground">{formatDate(m.joined_at)}</TableCell>
                <TableCell><RowActions member={m} actions={actions} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Móvil: tarjetas */}
      <ul className="space-y-3 md:hidden">
        {members.map((m) => (
          <li key={m.id} className="rounded-lg border border-border bg-background/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <Link to={`/members/${m.id}`} className="block truncate font-medium text-foreground hover:text-gold">
                  {m.full_name}
                </Link>
                <p className="text-xs tabular-nums text-muted-foreground">{m.identification}</p>
              </div>
              <MemberStatusBadge status={m.status} />
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground">Teléfono</dt>
                <dd className="tabular-nums">{formatPhone(m.phone)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Ingreso</dt>
                <dd>{formatDate(m.joined_at)}</dd>
              </div>
            </dl>
            <div className="mt-2 border-t border-border pt-2"><RowActions member={m} actions={actions} /></div>
          </li>
        ))}
      </ul>
    </>
  );
}
